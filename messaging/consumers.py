# messaging/consumers.py
import json
import logging
import asyncio
from channels.generic.websocket import (
    AsyncWebsocketConsumer,
    AsyncJsonWebsocketConsumer,
)
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from messaging.exceptions import (
    WebSocketAuthenticationError,
    WebSocketMessageError,
    ConversationAccessError,
    MessageDeliveryError,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # Get conversation ID from URL route
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.group_name = f"conversation_{self.conversation_id}"

            # Handle authentication
            if self.scope["user"].is_anonymous:
                logger.warning("Anonymous user attempted to connect")
                raise WebSocketAuthenticationError(
                    "Authentication required for WebSocket connection"
                )

            # Check conversation participant
            is_participant = await self.is_conversation_participant()
            if not is_participant:
                logger.warning(
                    f"User {self.scope['user'].username} is not a participant in conversation {self.conversation_id}"
                )
                raise ConversationAccessError(
                    f"User not authorized to access conversation {self.conversation_id}"
                )

            # Join the group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            # Update online presence to True (with error handling)
            try:
                await self.update_user_presence(True)
            except Exception as e:
                logger.error(f"Failed to update user presence: {str(e)}", exc_info=True)
                # Continue connection process even if presence update fails

            # Send success message
            await self.send(
                json.dumps(
                    {
                        "type": "connection_established",
                        "message": "Connected successfully",
                        "conversation_id": self.conversation_id,
                    }
                )
            )
            logger.info(
                f"User {self.scope['user'].username} connected to conversation {self.conversation_id}"
            )

        except WebSocketAuthenticationError as e:
            logger.warning(f"Authentication error: {str(e)}")
            await self.close(code=4003)
        except ConversationAccessError as e:
            logger.warning(f"Access error: {str(e)}")
            await self.close(code=4004)
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}", exc_info=True)
            await self.close(code=4000)

    async def disconnect(self, close_code):
        try:
            # Update online presence to False with retry mechanism
            if (
                hasattr(self, "scope")
                and "user" in self.scope
                and not self.scope["user"].is_anonymous
            ):
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        await self.update_user_presence(False)
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            logger.error(
                                f"Failed to update presence after {max_retries} attempts: {str(e)}"
                            )
                        else:
                            logger.warning(
                                f"Retrying presence update ({retry_count}/{max_retries}): {str(e)}"
                            )
                            await asyncio.sleep(0.5)

            # Log disconnect with reason
            if (
                hasattr(self, "scope")
                and "user" in self.scope
                and hasattr(self, "conversation_id")
            ):
                logger.info(
                    f"User {self.scope['user'].username} disconnected from conversation {self.conversation_id} "
                    f"with code {close_code}"
                )

            # Leave conversation group
            if hasattr(self, "group_name") and hasattr(self, "channel_name"):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )

        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            logger.debug(f"Received WebSocket message type: {message_type}")

            # Handle read receipts
            if message_type == "mark_read":
                message_id = data.get("message_id")
                if message_id:
                    success = await self.mark_message_as_read(message_id)
                    if success:
                        # Notify other participants
                        await self.channel_layer.group_send(
                            self.group_name,
                            {
                                "type": "read_receipt",
                                "user_id": str(self.scope["user"].id),
                                "username": self.scope["user"].username,
                                "message_id": message_id,
                            },
                        )
                    else:
                        logger.warning(f"Failed to mark message {message_id} as read")

            # Handle typing indicators
            elif message_type == "typing":
                is_typing = data.get("is_typing", False)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "typing_indicator",
                        "user_id": str(self.scope["user"].id),
                        "username": self.scope["user"].username,
                        "conversation_id": self.conversation_id,
                        "is_typing": is_typing,
                    },
                )

        except json.JSONDecodeError:
            logger.warning(
                f"Invalid JSON received from user {self.scope['user'].username}"
            )
            await self.send(
                json.dumps({"type": "error", "message": "Invalid message format"})
            )
        except WebSocketMessageError as e:
            logger.error(f"WebSocket message error: {str(e)}")
            await self.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}", exc_info=True)
            await self.send(
                json.dumps({"type": "error", "message": "Internal server error"})
            )

    async def conversation_message(self, event):
        """Send message to WebSocket"""
        try:
            message_data = event.get("message", {})
            event_type = message_data.get("event_type", "message_created")

            # Standardize message type
            await self.send(
                text_data=json.dumps(
                    {
                        "type": event_type,
                        "message": {
                            "id": message_data.get("id"),
                            "content": message_data.get("content"),
                            "sender_id": message_data.get("sender_id"),
                            "sender_name": message_data.get("sender_name"),
                            "conversation_id": message_data.get("conversation_id"),
                            "timestamp": message_data.get("timestamp"),
                            "message_type": message_data.get("message_type", "text"),
                        },
                    }
                )
            )

            logger.debug(
                f"Sent {event_type} message to client: {message_data.get('id')}"
            )
        except Exception as e:
            logger.error(f"Error sending conversation message: {str(e)}", exc_info=True)
            raise MessageDeliveryError(f"Failed to deliver message: {str(e)}")

    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "read_receipt",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "message_id": event["message_id"],
                    }
                )
            )
        except Exception as e:
            logger.error(f"Error sending read receipt: {str(e)}", exc_info=True)

    @database_sync_to_async
    def update_user_presence(self, is_online):
        user = self.scope["user"]
        if not user.is_authenticated:
            return

        user.online = is_online
        user.last_seen = None if is_online else timezone.now()
        user.save(update_fields=["online", "last_seen"])

        # Broadcast presence update
        async_to_sync(self.channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "presence.update",
                "online": is_online,
                "user_id": str(user.id),
            },
        )

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Validate JWT token and get user"""
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            return User.objects.get(id=user_id)
        except (TokenError, InvalidToken, User.DoesNotExist) as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}", exc_info=True)
            return None

    @database_sync_to_async
    def is_conversation_participant(self):
        """Check if user is a participant in the conversation"""
        user = self.scope["user"]
        try:
            from messaging.models.one_to_one import OneToOneConversation

            if OneToOneConversation.objects.filter(
                id=self.conversation_id, participants=user
            ).exists():
                return True

            from messaging.models.group import GroupConversation

            if GroupConversation.objects.filter(
                id=self.conversation_id, participants=user
            ).exists():
                return True

            from messaging.models.chatbot import ChatbotConversation

            if ChatbotConversation.objects.filter(
                id=self.conversation_id, user=user
            ).exists():
                return True

            logger.warning(
                f"User {user.username} attempted to access conversation {self.conversation_id} but is not a participant"
            )
            return False
        except Exception as e:
            logger.error(
                f"Error checking conversation participant: {str(e)}", exc_info=True
            )
            return False

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark a message as read by the current user"""
        try:
            user = self.scope["user"]
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage

            try:
                message = OneToOneMessage.objects.get(
                    id=message_id, conversation__participants=user
                )
                if hasattr(message, "read_by") and user not in message.read_by.all():
                    message.read_by.add(user)
                    logger.debug(
                        f"Marked one-to-one message {message_id} as read by {user.username}"
                    )
                return True
            except OneToOneMessage.DoesNotExist:
                pass

            try:
                message = GroupMessage.objects.get(
                    id=message_id, conversation__participants=user
                )
                if hasattr(message, "read_by") and user not in message.read_by.all():
                    message.read_by.add(user)
                    logger.debug(
                        f"Marked group message {message_id} as read by {user.username}"
                    )
                return True
            except GroupMessage.DoesNotExist:
                pass

            logger.warning(f"Message {message_id} not found for user {user.username}")
            return False

        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}", exc_info=True)
            return False

    # New handler for typing indicators
    async def typing_indicator(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "conversation_id": event["conversation_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    # New handler for presence updates
    async def presence_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event["user_id"],
                    "online": event["online"],
                }
            )
        )


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group_name = "presence"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("PresenceConsumer connected.")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("PresenceConsumer disconnected.")

    async def receive_json(self, content):
        # Example: simply echo the presence update back to the client
        await self.send_json(content)

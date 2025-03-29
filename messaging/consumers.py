#messaging/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

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
                await self.close(code=4003)
                return
                
            # Check conversation participant
            is_participant = await self.is_conversation_participant()
            if not is_participant:
                logger.warning("User is not a conversation participant")
                await self.close(code=4004)
                return

            # Join the group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            
            # Send success message
            await self.send(json.dumps({
                "type": "connection_established",
                "message": "Connected successfully"
            }))
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        try:
            # Log disconnect with reason
            if hasattr(self, 'scope') and 'user' in self.scope and hasattr(self, 'conversation_id'):
                logger.info(
                    f"User {self.scope['user'].username} disconnected from conversation {self.conversation_id} "
                    f"with code {close_code}"
                )
            
            # Leave conversation group
            if hasattr(self, 'group_name') and hasattr(self, 'channel_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                
        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            logger.debug(f"Received WebSocket message: {data}")

            # Handle read receipts
            if data.get("type") == "mark_read":
                message_id = data.get("message_id")
                if message_id:
                    await self.mark_message_as_read(message_id)
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

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received in WebSocket message")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}", exc_info=True)

    async def conversation_message(self, event):
        """Send message to WebSocket"""
        try:
            message_data = event.get("message", {})
            
            # Ensure we're sending the correct event structure
            await self.send(text_data=json.dumps({
                "type": "new_message",
                "message": {
                    "id": message_data.get("id"),
                    "content": message_data.get("content"),
                    "sender_id": message_data.get("sender_id"),
                    "sender_name": message_data.get("sender_name"),
                    "conversation_id": message_data.get("conversation_id"),
                    "timestamp": message_data.get("timestamp"),
                    "event_type": message_data.get("event_type", "new_message"),
                    "message_type": message_data.get("message_type", "text")
                }
            }))
            
            logger.debug(f"Sent message to client: {message_data.get('id')}")
        except Exception as e:
            logger.error(f"Error sending conversation message: {str(e)}", exc_info=True)

    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        try:
            await self.send(
                text_data=json.dumps({
                    "type": "read_receipt",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "message_id": event["message_id"],
                })
            )
        except Exception as e:
            logger.error(f"Error sending read receipt: {str(e)}", exc_info=True)

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Validate JWT token and get user"""
        try:
            # Validate token and get user
            access_token = AccessToken(token)
            user_id = access_token['user_id']
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
            # Try one-to-one conversation first
            from messaging.models.one_to_one import OneToOneConversation
            if OneToOneConversation.objects.filter(
                id=self.conversation_id, participants=user
            ).exists():
                return True

            # Try group conversation
            from messaging.models.group import GroupConversation
            if GroupConversation.objects.filter(
                id=self.conversation_id, participants=user
            ).exists():
                return True

            # Try chatbot conversation
            from messaging.models.chatbot import ChatbotConversation
            if ChatbotConversation.objects.filter(
                id=self.conversation_id, user=user
            ).exists():
                return True

            logger.warning(
                f"User {user.username} attempted to access conversation {self.conversation_id} "
                f"but is not a participant"
            )
            return False
        except Exception as e:
            logger.error(f"Error checking conversation participant: {str(e)}", exc_info=True)
            return False

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark a message as read by the current user"""
        try:
            user = self.scope["user"]
            
            # Try to find the message in different message types
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage
            
            # Check OneToOneMessage
            try:
                message = OneToOneMessage.objects.get(id=message_id, conversation__participants=user)
                if hasattr(message, 'read_by') and user not in message.read_by.all():
                    message.read_by.add(user)
                    logger.debug(f"Marked one-to-one message {message_id} as read by {user.username}")
                return True
            except OneToOneMessage.DoesNotExist:
                pass
                
            # Check GroupMessage
            try:
                message = GroupMessage.objects.get(id=message_id, conversation__participants=user)
                if hasattr(message, 'read_by') and user not in message.read_by.all():
                    message.read_by.add(user)
                    logger.debug(f"Marked group message {message_id} as read by {user.username}")
                return True
            except GroupMessage.DoesNotExist:
                pass
                
            logger.warning(f"Message {message_id} not found for user {user.username}")
            return False
            
        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}", exc_info=True)
            return False

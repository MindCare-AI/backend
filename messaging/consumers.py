# messaging/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from messaging.models.one_to_one import OneToOneMessage
from messaging.models.group import GroupMessage

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time messaging.
    Supports both one-to-one and group conversations.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user and conversation ID
            self.user = self.scope["user"]
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.conversation_group_name = f"conversation_{self.conversation_id}"
            self.user_group_name = f"user_{self.user.id}"

            # Check if user is anonymous
            if self.user.is_anonymous:
                logger.warning(f"Anonymous user tried to connect to {self.conversation_group_name}")
                await self.close()
                return

            # Validate user's access to the conversation
            has_access = await self.check_conversation_access()
            if not has_access:
                logger.warning(
                    f"User {self.user.id} tried to access unauthorized conversation {self.conversation_id}"
                )
                await self.close()
                return

            # Add to conversation group
            await self.channel_layer.group_add(
                self.conversation_group_name, self.channel_name
            )

            # Add to user-specific group for private notifications
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)

            # Accept the connection
            await self.accept()

            # Notify about user presence
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "user_online",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "timestamp": timezone.now().isoformat(),
                },
            )

            # Update user's online status
            await self.update_user_status(True)

            logger.info(
                f"User {self.user.id} connected to conversation {self.conversation_id}"
            )

        except Exception as e:
            logger.error(f"Error in connect: {str(e)}", exc_info=True)
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave conversation group
            await self.channel_layer.group_discard(
                self.conversation_group_name, self.channel_name
            )

            # Leave user-specific group
            if hasattr(self, "user_group_name"):
                await self.channel_layer.group_discard(
                    self.user_group_name, self.channel_name
                )

            # Update user's offline status if this is their last connection
            if hasattr(self, "user") and not self.user.is_anonymous:
                await self.update_user_status(False)

                # Notify about user going offline
                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "user_offline",
                        "user_id": str(self.user.id),
                        "username": self.user.username,
                        "timestamp": timezone.now().isoformat(),
                    },
                )

                logger.info(
                    f"User {self.user.id} disconnected from conversation {self.conversation_id}"
                )

        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket data"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Handle different message types
            if message_type == "message":
                await self.handle_new_message(data)
            elif message_type == "typing":
                await self.handle_typing_indicator(data)
            elif message_type == "read":
                await self.handle_read_receipt(data)
            elif message_type == "reaction":
                await self.handle_reaction(data)
            else:
                logger.warning(f"Unknown message type received: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}", exc_info=True)

    async def handle_new_message(self, data):
        """Handle a new message event"""
        content = data.get("content", "").strip()
        conversation_id = self.conversation_id
        message_type = data.get("message_type", "text")
        metadata = data.get("metadata", {})
        media_id = data.get("media_id")

        if not content and not media_id:
            return

        # Create the message in database
        message = await self.create_message(
            conversation_id, content, message_type, metadata, media_id
        )

        if message:
            # Prepare message data for WebSocket response
            message_data = {
                "id": str(message["id"]),
                "content": message["content"],
                "sender_id": str(message["sender_id"]),
                "sender_name": message["sender_name"],
                "conversation_id": str(conversation_id),
                "timestamp": message["timestamp"],
                "message_type": message_type,
                "media_url": message.get("media_url"),
                "metadata": metadata,
            }

            # Broadcast to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "chat.message",
                    "message": message_data,
                    "event": "new_message",
                },
            )

    async def handle_typing_indicator(self, data):
        """Handle typing indicator"""
        is_typing = data.get("is_typing", False)

        # Send to conversation group
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                "type": "typing.indicator",
                "user_id": str(self.user.id),
                "username": self.user.username,
                "is_typing": is_typing,
            },
        )

    async def handle_read_receipt(self, data):
        """Handle read receipt"""
        message_id = data.get("message_id")
        if not message_id:
            return

        # Mark as read in database
        success = await self.mark_message_read(message_id)
        if success:
            # Send to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "read.receipt",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "message_id": message_id,
                    "timestamp": timezone.now().isoformat(),
                },
            )

    async def handle_reaction(self, data):
        """Handle reaction event"""
        message_id = data.get("message_id")
        reaction = data.get("reaction")
        action = data.get("action", "add")

        if not message_id or not reaction:
            return

        # Update reaction in database
        await self.update_message_reaction(data)

    async def update_message_reaction(self, data):
        """Update message reaction in database"""
        message_id = data.get("message_id")
        reaction = data.get("reaction")
        action = data.get("action", "add")  # add or remove

        if not message_id or not reaction:
            return

        try:
            # Try one-to-one messages first
            try:
                message = OneToOneMessage.objects.get(id=message_id)
            except ObjectDoesNotExist:
                try:
                    message = GroupMessage.objects.get(id=message_id)
                except ObjectDoesNotExist:
                    logger.error(f"Message with id {message_id} not found")
                    return

            # Update reaction logic
            if action == "add":
                message.add_reaction(self.user, reaction)
            else:
                message.remove_reaction(self.user, reaction)

            # Send to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "message.reaction",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "message_id": message_id,
                    "reaction": reaction,
                    "action": action,
                },
            )

        except Exception as e:
            logger.error(f"Error updating message reaction: {str(e)}", exc_info=True)

    # Event handlers for messages sent via channel layer

    async def chat_message(self, event):
        """Handle chat.message event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "event": event.get("event", "new_message"),
                    "message": event["message"],
                }
            )
        )

    async def typing_indicator(self, event):
        """Handle typing.indicator event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def read_receipt(self, event):
        """Handle read.receipt event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read_receipt",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "message_id": event["message_id"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def message_reaction(self, event):
        """
        Handle message.reaction event and send to WebSocket
        This gets called when someone adds/removes a reaction
        """
        await self.send(text_data=json.dumps({
            "type": "reaction",
            "user_id": event["user_id"],
            "username": event["username"],
            "message_id": event["message_id"],
            "reaction": event["reaction"],
            "action": event["action"]
        }))

    async def participant_added(self, event):
        """Handle participant.added event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "participant_added",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "added_by": event["added_by"],
                }
            )
        )

    async def participant_removed(self, event):
        """Handle participant.removed event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "participant_removed",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "removed_by": event["removed_by"],
                }
            )
        )

    async def conversation_message(self, event):
        """Handle conversation.message event"""
        await self.send(text_data=json.dumps({"message": event["message"]}))

    async def user_online(self, event):
        """Handle user_online event"""
        if str(self.user.id) != event["user_id"]:  # Don't send to self
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence",
                        "event": "online",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    async def user_offline(self, event):
        """Handle user_offline event"""
        if str(self.user.id) != event["user_id"]:  # Don't send to self
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence",
                        "event": "offline",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    # Database operations

    @database_sync_to_async
    def check_conversation_access(self):
        """Check if user has access to this conversation"""
        try:
            # Determine if it's a one-to-one or group conversation
            from .models.one_to_one import OneToOneConversation
            from .models.group import GroupConversation

            # Try one-to-one first
            try:
                conversation = OneToOneConversation.objects.get(id=self.conversation_id)
                if conversation.participants.filter(id=self.user.id).exists():
                    self.conversation_type = "one_to_one"
                    return True
            except OneToOneConversation.DoesNotExist:
                pass

            # Try group
            try:
                conversation = GroupConversation.objects.get(id=self.conversation_id)
                if conversation.participants.filter(id=self.user.id).exists():
                    self.conversation_type = "group"
                    return True
            except GroupConversation.DoesNotExist:
                pass

            return False

        except Exception as e:
            logger.error(f"Error checking conversation access: {str(e)}", exc_info=True)
            return False

    @database_sync_to_async
    def create_message(self, conversation_id, content, message_type="text", metadata=None, media_id=None):
        """Create a new message in the database"""
        try:
            if metadata is None:
                metadata = {}

            # Get the appropriate message model based on conversation type
            if getattr(self, "conversation_type", None) == "one_to_one":
                from .models.one_to_one import OneToOneMessage, OneToOneConversation

                conversation = OneToOneConversation.objects.get(id=conversation_id)
                message = OneToOneMessage.objects.create(
                    conversation=conversation,
                    sender=self.user,
                    content=content,
                    message_type=message_type,
                    metadata=metadata,
                )
                if media_id:
                    from media_handler.models import MediaFile
                    media = MediaFile.objects.get(id=media_id)
                    message.media = media.file
                    message.save()

            else:  # group conversation
                from .models.group import GroupMessage, GroupConversation

                conversation = GroupConversation.objects.get(id=conversation_id)
                message = GroupMessage.objects.create(
                    conversation=conversation,
                    sender=self.user,
                    content=content,
                    message_type=message_type,
                    metadata=metadata,
                )
                if media_id:
                    from media_handler.models import MediaFile
                    media = MediaFile.objects.get(id=media_id)
                    message.media = media.file
                    message.save()

            # Update conversation last_activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])

            # Prepare response
            result = {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender.username,
                "timestamp": message.timestamp.isoformat(),
            }
            
            # Add media URL if present
            if message.media:
                result["media_url"] = message.media.url

            return result

        except Exception as e:
            logger.error(f"Error creating message: {str(e)}", exc_info=True)
            return None

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark a message as read by the current user"""
        try:
            # Try both message types
            from .models.one_to_one import OneToOneMessage
            from .models.group import GroupMessage

            try:
                message = OneToOneMessage.objects.get(id=message_id)
                message.read_by.add(self.user)
                return True
            except OneToOneMessage.DoesNotExist:
                try:
                    message = GroupMessage.objects.get(id=message_id)
                    message.read_by.add(self.user)
                    return True
                except GroupMessage.DoesNotExist:
                    logger.warning(f"Message {message_id} not found for read receipt")
                    return False

        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}", exc_info=True)
            return False

    @database_sync_to_async
    def update_user_status(self, online_status):
        """Update user's online status"""
        try:
            self.user.is_online = online_status
            self.user.last_seen = timezone.now()
            self.user.save(update_fields=["is_online", "last_seen"])
            return True
        except Exception as e:
            logger.error(f"Error updating user status: {str(e)}", exc_info=True)
            return False

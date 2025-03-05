# messaging/models.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]

        # Verify conversation access
        if not await self.verify_conversation_access():
            await self.close(code=4003)
            return

        self.conversation_group_name = f"chat_{self.conversation_id}"

        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name, self.channel_name
        )
        await self.accept()

    @sync_to_async
    def verify_conversation_access(self):
        """Verify that the user has access to the conversation"""
        try:
            self.conversation = Conversation.objects.get(pk=self.conversation_id)
            return self.user in self.conversation.participants.all()
        except Conversation.DoesNotExist:
            return False

    async def disconnect(self, close_code):
        # Leave conversation group
        if hasattr(self, "conversation_group_name"):
            await self.channel_layer.group_discard(
                self.conversation_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get("type", "message")

            handlers = {
                "message": self.handle_message,
                "typing": self.handle_typing,
                "read_receipt": self.handle_read_receipt,
            }

            handler = handlers.get(event_type)
            if handler:
                await handler(data)
            else:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": f"Unsupported event type: {event_type}",
                        }
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )

    async def handle_message(self, data):
        message = data.get("message", "").strip()
        if not message:
            return

        # Save message to database
        message_obj = await sync_to_async(Message.objects.create)(
            conversation_id=self.conversation_id,
            sender=self.user,
            content=message,
            message_type="text",
        )

        # Update conversation last message
        await sync_to_async(message_obj.conversation.update_last_message)()

        # Broadcast message to group
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": self.user.username,
                "timestamp": str(message_obj.timestamp),
                "message_id": message_obj.id,
            },
        )

    async def handle_typing(self, data):
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                "type": "typing_indicator",
                "user": self.user.username,
                "is_typing": data.get("is_typing", False),
            },
        )

    async def handle_read_receipt(self, data):
        message_id = data.get("message_id")

        if message_id:
            try:
                message = await sync_to_async(Message.objects.get)(id=message_id)
                if message.conversation_id != int(self.conversation_id):
                    return  # Ignore read receipts for messages from other conversations

                await sync_to_async(message.mark_read)(self.user)

                await self.channel_layer.group_send(
                    self.conversation_group_name,
                    {
                        "type": "read_receipt",
                        "message_id": message_id,
                        "read_by": self.user.username,
                    },
                )
            except Message.DoesNotExist:
                pass

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event["message"],
                    "sender": event["sender"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                }
            )
        )

    async def typing_indicator(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user": event["user"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read",
                    "message_id": event["message_id"],
                    "read_by": event["read_by"],
                }
            )
        )

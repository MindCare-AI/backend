#messaging/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from .throttling import TypingIndicatorThrottle
from .models import OneToOneConversation
import json


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        conversation_id = self.scope['url_route']['kwargs']['room_name']
        if not OneToOneConversation.objects.filter(
            id=conversation_id, participants=user
        ).exists():
            await self.close()
            return

        await self.channel_layer.group_add(
            f"chat_{conversation_id}",
            self.channel_name
        )
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data["type"] == "typing":
            # Check throttling
            if self.typing_throttler.allow_request(self.scope["request"], None):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "typing_indicator",
                        "user_id": self.scope["user"].id,
                        "is_typing": data["is_typing"],
                    },
                )

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

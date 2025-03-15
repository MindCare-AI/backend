#messaging/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import PermissionDenied
import json
from .models import OneToOneConversation


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                raise AuthenticationFailed("Authentication required")
            
            self.conversation_id = self.scope["url_route"]["kwargs"]["room_name"]
            conversation = await sync_to_async(OneToOneConversation.objects.get)(id=self.conversation_id)
            
            # Verify that the user is a participant of the conversation
            if not await sync_to_async(conversation.participants.filter(id=user.id).exists)():
                raise PermissionDenied("Not a conversation participant")
            
            await self.channel_layer.group_add(
                f"chat_{self.conversation_id}",
                self.channel_name
            )
            await self.accept()
        except Exception as e:
            # Optionally log the error here
            await self.close(code=4001)

    async def receive(self, text_data):
        data = json.loads(text_data)
        # Process incoming data as needed, for example handling typing indicators or messages.

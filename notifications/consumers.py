# notifications/consumers.py
# notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                raise AuthenticationFailed("WebSocket authentication required")
                
            # Validate notification permissions
            if not user.has_perm('notifications.receive_notifications'):
                raise PermissionDenied("Notification access denied")

            self.user_group = f"notifications_{user.id}"
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            await self.accept()
            await self.send_json({"status": "connected"})
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.close(code=4001)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "user_group"):
                await self.channel_layer.group_discard(self.user_group, self.channel_name)
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {str(e)}")

    async def notification_message(self, event):
        try:
            await self.send_json(event["content"])
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
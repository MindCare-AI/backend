# notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection with authentication"""
        try:
            # Verify authentication
            if self.scope["user"].is_anonymous:
                await self.close()
                return

            # Add user to their notification group
            self.user_group = f"notifications_{self.scope['user'].id}"
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            await self.accept()

        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        """Clean up on disconnect"""
        try:
            if hasattr(self, "user_group"):
                await self.channel_layer.group_discard(
                    self.user_group, self.channel_name
                )
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {str(e)}")

    async def notification_message(self, event):
        """Send notification to WebSocket"""
        try:
            await self.send_json(event["content"])
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

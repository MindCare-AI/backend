# notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            logger.warning(
                "Anonymous user attempted to connect to notification websocket"
            )
            await self.close()
            return

        self.group_name = f"user_{self.scope['user'].id}_notifications"

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                f"User {self.scope['user'].username} connected to notifications"
            )
        except Exception as e:
            logger.error(f"Error in websocket connection: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
                logger.info(
                    f"User {self.scope['user'].username} disconnected from notifications"
                )
        except Exception as e:
            logger.error(f"Error in websocket disconnection: {str(e)}")

    async def receive_json(self, content):
        # Handle incoming messages if needed
        pass

    async def notification_message(self, event):
        try:
            await self.send_json(event["message"])
        except Exception as e:
            logger.error(f"Error sending notification message: {str(e)}")
            await self.close()

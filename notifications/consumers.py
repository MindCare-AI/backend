# notifications/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling user notifications.
    """

    async def connect(self) -> None:
        """
        Handle WebSocket connection.
        """
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        try:
            await self.channel_layer.group_add(f"user_{user.id}", self.channel_name)
            await self.accept()
            asyncio.create_task(self.heartbeat())
        except Exception:
            logger.exception(
                "WebSocket connection failed for user %s",
                getattr(user, "username", "Unknown"),
            )
            await self.close()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        """
        user = self.scope.get("user")
        if user and user.is_authenticated:
            try:
                await self.channel_layer.group_discard(
                    f"user_{user.id}", self.channel_name
                )
            except Exception:
                logger.exception("Error during disconnect for user %s", user.id)

    async def receive(self, text_data):
        """
        Handle received WebSocket messages.
        """
        try:
            data = json.loads(text_data)
            if data.get("type") == "pong":
                logger.info("Received pong from websocket")
            else:
                # Process other received data here...
                pass
        except json.JSONDecodeError:
            logger.error("Received invalid JSON data.")
            await self.close()

    async def send_notification(self, event):
        """
        Send notification to the WebSocket.
        """
        try:
            await self.send(text_data=json.dumps(event["notification"]))
            logger.info(
                "Notification sent via WebSocket to channel %s", self.channel_name
            )
        except Exception:
            logger.exception("Failed to send notification")

    async def heartbeat(self):
        try:
            while True:
                await self.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(30)
        except Exception:
            logger.exception("Heartbeat failed")
            await self.close()

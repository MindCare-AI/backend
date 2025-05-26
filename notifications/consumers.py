# notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging
import asyncio
from django.utils import timezone
from django.conf import settings

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
        self.last_ping = timezone.now()
        self.heartbeat_interval = getattr(settings, "WEBSOCKET_HEARTBEAT_INTERVAL", 30)
        self.heartbeat_task = None

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                f"User {self.scope['user'].username} connected to notifications"
            )

            # Start heartbeat task to monitor connection health
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
        except Exception as e:
            logger.error(f"Error in websocket connection: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            # Cancel the heartbeat task if it exists
            if self.heartbeat_task:
                self.heartbeat_task.cancel()

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
        try:
            msg_type = content.get("type")

            # Handle ping/pong for heartbeat
            if msg_type == "ping":
                self.last_ping = timezone.now()
                await self.send_json({"type": "pong"})
            # Handle client reconnection acknowledgment
            elif msg_type == "reconnect":
                logger.info(f"User {self.scope['user'].username} reconnected")
                self.last_ping = timezone.now()
                await self.send_json({"type": "reconnect_ack", "success": True})
        except Exception as e:
            logger.error(f"Error processing received message: {str(e)}")

    async def notification_message(self, event):
        try:
            await self.send_json(event["message"])
        except Exception as e:
            logger.error(f"Error sending notification message: {str(e)}")
            await self.close()

    async def send_heartbeat(self):
        """Send periodic heartbeats to ensure connection is still alive"""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if connection is stale
                time_since_last_ping = (timezone.now() - self.last_ping).total_seconds()
                if time_since_last_ping > self.heartbeat_interval * 3:
                    logger.warning(
                        f"Connection stale for user {self.scope['user'].username}, closing"
                    )
                    await self.close(
                        code=4000
                    )  # Custom close code for stale connection
                    break

                # Send heartbeat ping
                await self.send_json({"type": "heartbeat"})
        except asyncio.CancelledError:
            # Task was cancelled during disconnect, this is normal
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat task: {str(e)}")
            await self.close(code=4001)  # Custom close code for heartbeat error

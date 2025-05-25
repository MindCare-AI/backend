# messaging/services/connection_manager.py
import logging
from datetime import timedelta
from channels.layers import get_channel_layer
from django.utils import timezone
from django.conf import settings
import asyncio

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Service for managing WebSocket connections state, including:
    - Tracking active connections
    - Detecting stale connections
    - Performing cleanup operations
    """

    def __init__(self):
        self.active_connections = {}  # Map of user_id -> {connection_info}
        self.channel_layer = get_channel_layer()
        self.stale_threshold = getattr(
            settings, "WEBSOCKET_STALE_THRESHOLD", 120
        )  # seconds
        self.cleanup_interval = getattr(
            settings, "WEBSOCKET_CLEANUP_INTERVAL", 300
        )  # seconds

    def register_connection(self, user_id, channel_name, connection_type="messaging"):
        """Register a new WebSocket connection"""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}

        self.active_connections[user_id][channel_name] = {
            "type": connection_type,
            "connected_at": timezone.now(),
            "last_activity": timezone.now(),
        }

        logger.info(
            f"Registered WebSocket connection for user {user_id}: {channel_name}"
        )

    def update_connection_activity(self, user_id, channel_name):
        """Update the last activity timestamp for a connection"""
        if (
            user_id in self.active_connections
            and channel_name in self.active_connections[user_id]
        ):
            self.active_connections[user_id][channel_name]["last_activity"] = (
                timezone.now()
            )

    def unregister_connection(self, user_id, channel_name):
        """Unregister a WebSocket connection when it's closed"""
        if user_id in self.active_connections:
            if channel_name in self.active_connections[user_id]:
                del self.active_connections[user_id][channel_name]
                logger.info(
                    f"Unregistered WebSocket connection for user {user_id}: {channel_name}"
                )

            # If no more connections for this user, remove the user entry
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    def get_active_connections_count(self):
        """Get number of active connections"""
        connection_count = 0
        for user_id, connections in self.active_connections.items():
            connection_count += len(connections)
        return connection_count

    def get_user_connection_count(self, user_id):
        """Get number of active connections for a specific user"""
        if user_id in self.active_connections:
            return len(self.active_connections[user_id])
        return 0

    def is_user_online(self, user_id):
        """Check if a user has any active connections"""
        return (
            user_id in self.active_connections
            and len(self.active_connections[user_id]) > 0
        )

    async def cleanup_stale_connections(self):
        """Check and close stale connections"""
        now = timezone.now()
        stale_threshold = now - timedelta(seconds=self.stale_threshold)

        stale_connections = []

        # Identify stale connections
        for user_id, connections in self.active_connections.items():
            for channel_name, conn_info in connections.items():
                if conn_info["last_activity"] < stale_threshold:
                    stale_connections.append((user_id, channel_name))

        # Close stale connections
        for user_id, channel_name in stale_connections:
            logger.warning(
                f"Closing stale connection for user {user_id}: {channel_name}"
            )
            try:
                # Send close message to the connection
                await self.channel_layer.send(
                    channel_name,
                    {
                        "type": "websocket.close",
                        "code": 4000,  # Custom code for stale connection
                    },
                )

                # Remove from our tracking
                self.unregister_connection(user_id, channel_name)
            except Exception as e:
                logger.error(f"Error closing stale connection: {str(e)}")

    async def start_cleanup_task(self):
        """Start periodic cleanup task"""
        while True:
            try:
                await self.cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in connection cleanup: {str(e)}")

            await asyncio.sleep(self.cleanup_interval)


# Create a singleton instance
connection_manager = WebSocketConnectionManager()

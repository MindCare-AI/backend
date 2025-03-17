# notifications/services/websocket_service.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from ..models import Notification
import logging

logger = logging.getLogger(__name__)


class WebSocketService:
    @staticmethod
    def send_websocket_notification(user_id: int, notification: Notification) -> None:
        channel_layer = get_channel_layer()
        notification_data = {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority,
            "category": notification.category,
        }

        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                "type": "send_notification",
                "notification": notification_data,
            },
        )

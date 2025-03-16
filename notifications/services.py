# notifications/services.py
from collections import defaultdict
import logging
from django.db import transaction
from typing import Optional, List
from django.utils import timezone
from .models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notification creation and delivery"""

    def create_notification(
        self,
        user,
        message: str,
        notification_type: str = "info",
        priority: str = "normal",
        url: Optional[str] = None,
        expires_at: Optional[timezone.datetime] = None,
    ) -> Optional[Notification]:
        """Create a single notification"""
        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    user=user,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    url=url,
                    expires_at=expires_at,
                )

                self._notify_client(notification)
                return notification

        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None

    def create_group_notification(
        self, group, message: str, exclude_users: List = None, **kwargs
    ) -> List[Notification]:
        """Create notifications for group members"""
        try:
            notifications = []
            exclude_users = exclude_users or []

            with transaction.atomic():
                users = group.participants.exclude(id__in=[u.id for u in exclude_users])

                for user in users:
                    notification = self.create_notification(
                        user=user, message=message, **kwargs
                    )
                    if notification:
                        notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error(f"Failed to create group notifications: {str(e)}")
            return []

    def create_bulk_notifications(self, users, message, **kwargs):
        """Bulk create notifications with significantly fewer queries"""
        try:
            notifications = [
                Notification(user=user, message=message, **kwargs) for user in users
            ]

            created = Notification.objects.bulk_create(notifications, batch_size=500)
            self._send_bulk_ws_notifications(created)
            return created

        except Exception as e:
            logger.error(f"Bulk notification error: {str(e)}")
            return []

    def delete_old_notifications(self, days=30):
        """Delete notifications older than specified days"""
        try:
            import datetime

            cutoff_date = timezone.now() - datetime.timedelta(days=days)
            deleted_count, _ = Notification.objects.filter(
                created_at__lt=cutoff_date, is_read=True
            ).delete()

            logger.info(f"Deleted {deleted_count} old notifications")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete old notifications: {str(e)}")
            return 0

    def mark_as_read(self, notification_ids: List[int], user) -> int:
        """Mark multiple notifications as read"""
        try:
            count = Notification.objects.filter(
                id__in=notification_ids, user=user, is_read=False
            ).update(is_read=True, read_at=timezone.now())
            return count
        except Exception as e:
            logger.error(f"Failed to mark notifications as read: {str(e)}")
            return 0

    def _notify_client(self, notification):
        """Send real-time notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"notifications_{notification.user.id}",
                {
                    "type": "notification.message",
                    "message": {
                        "id": notification.id,
                        "message": notification.message,
                        "type": notification.notification_type,
                        "priority": notification.priority,
                        "url": notification.url,
                    },
                },
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {str(e)}")

    def _send_bulk_ws_notifications(self, notifications):
        """Batch WebSocket notifications by grouping messages per user"""
        try:
            grouped = defaultdict(list)

            for notification in notifications:
                grouped[notification.user.id].append(
                    {
                        "id": notification.id,
                        "message": notification.message,
                        "type": notification.notification_type,
                    }
                )

            channel_layer = get_channel_layer()
            for user_id, messages in grouped.items():
                async_to_sync(channel_layer.group_send)(
                    f"notifications_{user_id}",
                    {"type": "notification.message", "messages": messages},
                )

        except Exception as e:
            logger.error(f"Bulk WS error: {str(e)}")

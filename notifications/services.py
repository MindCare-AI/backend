#notifications/services.py
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging
from typing import List, Optional
from .models import Notification

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling notification creation and delivery"""

    def create_notification(
        self, 
        user, 
        message: str, 
        notification_type: str = 'info',
        priority: str = 'normal',
        url: Optional[str] = None,
        expires_at: Optional[timezone.datetime] = None
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
                    expires_at=expires_at
                )
                
                self._notify_client(notification)
                return notification

        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None

    def create_group_notification(
        self,
        group,
        message: str,
        exclude_users: List = None,
        **kwargs
    ) -> List[Notification]:
        """Create notifications for group members"""
        try:
            notifications = []
            exclude_users = exclude_users or []

            with transaction.atomic():
                users = group.participants.exclude(
                    id__in=[u.id for u in exclude_users]
                )

                for user in users:
                    notification = self.create_notification(
                        user=user,
                        message=message,
                        **kwargs
                    )
                    if notification:
                        notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error(f"Failed to create group notifications: {str(e)}")
            return []

    def create_bulk_notifications(
        self, users, message, notification_type="info", url=None
    ):
        """Create notifications for multiple users"""
        try:
            notifications = []
            with transaction.atomic():
                for user in users:
                    notification = Notification.objects.create(
                        user=user,
                        message=message,
                        notification_type=notification_type,
                        url=url,
                    )
                    notifications.append(notification)

            logger.info(f"Created {len(notifications)} bulk notifications")
            return notifications
        except Exception as e:
            logger.error(f"Failed to create bulk notifications: {str(e)}")
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
                id__in=notification_ids,
                user=user,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
            return count
        except Exception as e:
            logger.error(f"Failed to mark notifications as read: {str(e)}")
            return 0

    def _notify_client(self, notification):
        """Send real-time notification via WebSocket"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
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
                        "url": notification.url
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {str(e)}")

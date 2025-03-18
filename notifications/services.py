# notifications/services.py
from .models import Notification, NotificationType
from users.models import UserPreferences
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class UnifiedNotificationService:
    def __init__(self):
        self.type_cache = {}

    def get_or_create_notification_type(self, type_name):
        """Get or create a notification type with default settings."""
        try:
            notification_type = NotificationType.objects.get(name=type_name)
            logger.info(f"Found existing notification type: {type_name}")
        except NotificationType.DoesNotExist:
            notification_type = NotificationType.objects.create(
                name=type_name,
                description=f"Notification type for {type_name}",
                default_enabled=True,
                is_global=True,
            )
            logger.info(f"Created new notification type: {type_name}")
        return notification_type

    def send_notification(self, user, notification_type_name, title, message, **kwargs):
        try:
            # Ensure notification type exists
            notification_type = self.get_or_create_notification_type(
                notification_type_name
            )

            # Check user preferences
            preferences = UserPreferences.objects.get_or_create(user=user)[0]
            if not self._check_notification_allowed(preferences, notification_type):
                logger.debug(
                    f"Notification {notification_type_name} not allowed for {user}"
                )
                return None

            # Create notification
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=kwargs.get("priority", "medium"),
                metadata=kwargs.get("metadata", {}),
                content_object=kwargs.get("content_object"),
            )

            # Handle different channels
            if kwargs.get("send_email", False):
                self._send_email_notification(user, notification, preferences)

            if kwargs.get("send_in_app", True):
                self._send_in_app_notification(user, notification)

            return notification

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            if kwargs.get("send_in_app", True):
                self._send_in_app_notification(user, notification)

            return notification

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return None

    def _check_notification_allowed(self, preferences, notification_type):
        # Check global enable/disable first
        if not preferences.in_app_notifications:
            return False

        # Check type-specific settings
        if notification_type.is_global:
            return (
                notification_type.default_enabled
                and not preferences.disabled_notification_types.filter(
                    id=notification_type.id
                ).exists()
            )
        else:
            return notification_type.default_enabled

    def _send_email_notification(self, user, notification, preferences):
        if preferences.email_notifications:
            # Implement actual email sending logic here
            logger.info(f"Sent email notification to {user.email}")

    def _send_in_app_notification(self, user, notification):
        try:
            channel_layer = get_channel_layer()
            notification_data = {
                "id": notification.id,
                "type": notification.notification_type.name,
                "title": notification.title,
                "message": notification.message,
                "timestamp": notification.created_at.isoformat(),
                "priority": notification.priority,
            }

            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}_notifications",
                {"type": "notification.message", "message": notification_data},
            )
            logger.info(f"Sent WebSocket notification to user {user.username}")
            return True

        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {str(e)}")
            return False

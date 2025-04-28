# notifications/services.py
from .models import Notification, NotificationType
from users.models import UserPreferences
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class UnifiedNotificationService:
    def __init__(self):
        self.type_cache = {}
        self.cache_timeout = getattr(settings, "NOTIFICATION_CACHE_TIMEOUT", 3600)

    def get_or_create_notification_type(self, type_name):
        """Get or create a notification type with caching."""
        cache_key = f"notification_type_{type_name}"
        notification_type = cache.get(cache_key)

        if notification_type is None:
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

            # Cache the notification type
            cache.set(cache_key, notification_type, timeout=self.cache_timeout)

        return notification_type

    def send_notification(self, user, notification_type_name, title, message, **kwargs):
        try:
            # Get notification type using cached method
            notification_type = self.get_or_create_notification_type(
                notification_type_name
            )

            # Get cached preferences
            pref_cache_key = f"user_preferences_{user.id}"
            preferences = cache.get(pref_cache_key)

            if preferences is None:
                preferences, _ = UserPreferences.objects.get_or_create(user=user)
                cache.set(pref_cache_key, preferences, timeout=self.cache_timeout)

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

            # Invalidate relevant caches
            self._invalidate_user_caches(user.id)

            # Handle different channels
            if kwargs.get("send_email", False):
                self._send_email_notification(user, notification, preferences)

            if kwargs.get("send_in_app", True):
                self._send_in_app_notification(user, notification)

            return notification

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return None

    def _invalidate_user_caches(self, user_id):
        """Invalidate all caches related to a user's notifications."""
        cache_keys = [
            f"user_notifications_{user_id}",
            f"notification_count_{user_id}",
            f"user_preferences_{user_id}",
        ]
        cache.delete_many(cache_keys)

    def _check_notification_allowed(self, preferences, notification_type):
        """Check if notification is allowed with caching."""
        cache_key = f"notification_allowed_{preferences.user.id}_{notification_type.id}"
        allowed = cache.get(cache_key)

        if allowed is None:
            allowed = preferences.in_app_notifications
            cache.set(cache_key, allowed, timeout=300)  # Cache for 5 minutes

        return allowed

    def _send_email_notification(self, user, notification, preferences):
        if preferences.email_notifications:
            # Implement actual email sending logic here.
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

    def get_notification_data(self, notification_id):
        cache_key = f"notif_data_{notification_id}"
        data = cache.get(cache_key)
        if data:
            return data
        # Implement actual processing logic here.
        cache.set(cache_key, data, 300)
        return data

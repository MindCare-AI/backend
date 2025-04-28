# notifications/signals.py
from django.db.models.signals import post_migrate, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import NotificationType, Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_TYPES = [
    ("system_alert", "Important system alerts and updates", True),
    ("appointment_reminder", "Notifications about upcoming appointments", True),
    ("appointment_request", "New appointment requests from patients", True),
    ("appointment_requested", "Confirmation of appointment request submission", True),
    ("appointment_confirmed", "Notifications when appointments are confirmed", True),
    ("appointment_rescheduled", "Notifications about rescheduled appointments", True),
    ("appointment_cancelled", "Notifications about cancelled appointments", True),
    ("new_message", "Notifications about new messages", True),
    ("therapy_update", "Updates from therapy sessions", True),
    ("security_alert", "Security-related notifications", True),
    ("one_to_one_message", "Notification for new direct messages", True),
]


@receiver(post_migrate)
def create_default_notification_types(sender, **kwargs):
    """Create default notification types after migrations."""
    if sender.name == "notifications":
        for name, desc, is_global in DEFAULT_NOTIFICATION_TYPES:
            try:
                NotificationType.objects.get_or_create(
                    name=name,
                    defaults={
                        "description": desc,
                        "default_enabled": True,
                        "is_global": is_global,
                    },
                )
            except Exception as e:
                logger.error(f"Error creating notification type {name}: {str(e)}")


@receiver(post_save, sender=Notification)
def notification_post_save(sender, instance, created, **kwargs):
    """Handle notification creation/update with cache invalidation"""
    try:
        # Invalidate user's notification caches
        cache_keys = [
            f"user_notifications_{instance.user.id}",
            f"notification_count_{instance.user.id}",
            f"user_unread_notifications_{instance.user.id}",
        ]
        cache.delete_many(cache_keys)

        # Send WebSocket notification only for new notifications
        if created:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{instance.user.id}_notifications",
                {
                    "type": "notification.message",
                    "message": {
                        "id": str(instance.id),
                        "type": instance.notification_type.name,
                        "title": instance.title,
                        "message": instance.message,
                        "timestamp": instance.created_at.isoformat(),
                        "priority": instance.priority,
                        "read": instance.read,
                    },
                },
            )
    except Exception as e:
        logger.error(f"Error in notification post_save signal: {str(e)}", exc_info=True)


@receiver([pre_delete, post_delete], sender=Notification)
def notification_delete(sender, instance, **kwargs):
    """Handle notification deletion with cache cleanup"""
    try:
        # Invalidate all related caches
        cache_keys = [
            f"user_notifications_{instance.user.id}",
            f"notification_count_{instance.user.id}",
            f"user_unread_notifications_{instance.user.id}",
            f"notification_{instance.id}",
        ]
        cache.delete_many(cache_keys)

    except Exception as e:
        logger.error(f"Error in notification delete signal: {str(e)}", exc_info=True)


def notification_handler(sender, instance, **kwargs):
    cache_key = f"notification_{instance.id}"
    if cached := cache.get(cache_key):
        return cached
    # ...existing notification handling code...
    cache.set(cache_key, instance, 300)
    return instance


def bulk_create_notifications(notifications_data):
    """
    Efficiently create multiple notifications with proper cache handling

    Args:
        notifications_data: List of dictionaries containing notification data
    """
    try:
        # Group notifications by user for efficient cache invalidation
        user_notifications = {}
        notifications_to_create = []

        for data in notifications_data:
            user = data["user"]
            notification_type = data.get(
                "notification_type"
            ) or NotificationType.objects.get(name=data["notification_type_name"])

            notification = Notification(
                user=user,
                notification_type=notification_type,
                title=data["title"],
                message=data["message"],
                priority=data.get("priority", "medium"),
                metadata=data.get("metadata", {}),
            )
            notifications_to_create.append(notification)

            if user.id not in user_notifications:
                user_notifications[user.id] = []
            user_notifications[user.id].append(notification)

        # Bulk create all notifications
        created_notifications = Notification.objects.bulk_create(
            notifications_to_create
        )

        # Invalidate caches and send WebSocket notifications for each user
        channel_layer = get_channel_layer()

        for user_id, user_notifs in user_notifications.items():
            # Invalidate user's caches
            cache_keys = [
                f"user_notifications_{user_id}",
                f"notification_count_{user_id}",
                f"user_unread_notifications_{user_id}",
            ]
            cache.delete_many(cache_keys)

            # Send WebSocket notifications
            for notification in user_notifs:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}_notifications",
                    {
                        "type": "notification.message",
                        "message": {
                            "id": str(notification.id),
                            "type": notification.notification_type.name,
                            "title": notification.title,
                            "message": notification.message,
                            "timestamp": notification.created_at.isoformat(),
                            "priority": notification.priority,
                            "read": notification.read,
                        },
                    },
                )

        return created_notifications

    except Exception as e:
        logger.error(f"Error in bulk_create_notifications: {str(e)}", exc_info=True)
        raise

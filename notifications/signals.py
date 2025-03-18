# notifications/signals.py
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from .models import NotificationType, Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_TYPES = [
    ("system_alert", "Important system alerts and updates", True),
    ("appointment_reminder", "Notifications about upcoming appointments", True),
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
def send_notification_websocket(sender, instance, created, **kwargs):
    """Send WebSocket notification when a new notification is created."""
    if created:
        try:
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
                    },
                },
            )
        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {str(e)}")

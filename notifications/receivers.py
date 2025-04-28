# notifications/receivers.py
import logging
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.cache import cache
from .models import NotificationType

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_TYPES = [
    ("system_alert", "Important system alerts and updates"),
    ("appointment_reminder", "Notifications about upcoming appointments"),
    ("new_message", "Notifications about new messages"),
    ("therapy_update", "Updates from therapy sessions"),
    ("security_alert", "Security-related notifications"),
]


@receiver(post_migrate)
def create_default_notification_types(sender, **kwargs):
    """Create default notification types with cache handling"""
    if sender.name == "notifications":
        # Bulk create notification types
        types_to_create = []
        for name, desc in DEFAULT_NOTIFICATION_TYPES:
            try:
                # Check if type exists
                notification_type = NotificationType.objects.filter(name=name).first()
                if not notification_type:
                    types_to_create.append(
                        NotificationType(
                            name=name,
                            description=desc,
                            default_enabled=True,
                            is_global=True,
                        )
                    )
            except Exception as e:
                logger.error(f"Error processing notification type {name}: {str(e)}")

        if types_to_create:
            NotificationType.objects.bulk_create(types_to_create)

            # Invalidate notification type cache after bulk create
            cache.delete_pattern("notification_type_*")
            cache.delete("all_notification_types")


def receive_notification(sender, **kwargs):
    notification = kwargs.get("notification")
    cache_key = f"notif_{notification.id}"
    if cache.get(cache_key):
        return
    # ...existing receiver code...
    cache.set(cache_key, True, 300)

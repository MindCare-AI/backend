# notifications/receivers.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import NotificationType

DEFAULT_NOTIFICATION_TYPES = [
    ("system_alert", "Important system alerts and updates"),
    ("appointment_reminder", "Notifications about upcoming appointments"),
    ("new_message", "Notifications about new messages"),
    ("therapy_update", "Updates from therapy sessions"),
    ("security_alert", "Security-related notifications"),
]


@receiver(post_migrate)
def create_default_notification_types(sender, **kwargs):
    if sender.name == "notifications":
        for name, desc in DEFAULT_NOTIFICATION_TYPES:
            NotificationType.objects.get_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "default_enabled": True,
                    "is_global": True,
                },
            )

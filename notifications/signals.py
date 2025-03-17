# notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import NotificationPreference, Notification
from notifications.services import NotificationService
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def send_websocket_notification(sender, instance, created, **kwargs):
    if created:
        try:
            NotificationService.send_websocket_notification(instance.user_id, instance)
            instance.websocket_sent = True
            instance.save()
        except Exception:
            logger.exception("Failed to send websocket notification")


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    if created:
        try:
            NotificationPreference.objects.get_or_create(user=instance)
        except Exception:
            logger.exception(
                "Error creating NotificationPreference for user %s", instance.id
            )

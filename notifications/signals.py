# notifications/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from messaging.models import OneToOneMessage, GroupMessage
from .models import Notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OneToOneMessage)
def create_message_notification(sender, instance, created, **kwargs):
    if created and not Notification.objects.filter(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.id
    ).exists():
        try:
            participants = instance.conversation.participants.exclude(
                id=instance.sender.id
            )
            for user in participants:
                Notification.objects.create(
                    user=user,
                    message=f"New message from {instance.sender.username}",
                    notification_type="message",
                    content_object=instance,
                    url=instance.conversation.get_absolute_url(),  # Dynamic URL
                )
        except Exception as e:
            logger.error(f"Error creating message notification: {str(e)}")


@receiver(post_save, sender=GroupMessage)
def create_group_message_notification(sender, instance, created, **kwargs):
    if created:
        try:
            participants = instance.conversation.participants.exclude(
                id=instance.sender.id
            )
            for user in participants:
                Notification.objects.create(
                    user=user,
                    message=f"New message in {instance.conversation.name}",
                    notification_type="message",
                    content_object=instance,
                    url=f"/groups/{instance.conversation.id}/",
                )
        except Exception as e:
            logger.error(f"Error creating group message notification: {str(e)}")

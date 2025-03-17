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
    if created:
        try:
            # Import user preferences to check notification settings
            from users.models import UserPreferences
            
            participants = instance.conversation.participants.exclude(
                id=instance.sender.id
            ).prefetch_related('preferences')
            
            notifications = []
            for user in participants:
                # Only send notification if user's preferences allow message notifications
                if not UserPreferences.objects.filter(
                    user=user,
                    notification_preferences__message_notifications=True
                ).exists():
                    continue
                
                # Set high priority if the user is the therapist (if applicable)
                priority = 'high' if hasattr(instance.conversation, 'therapist') and user == instance.conversation.therapist else 'normal'
                
                notifications.append(Notification(
                    user=user,
                    message=f"New message from {instance.sender.username}",
                    notification_type="message",
                    content_object=instance,
                    url=instance.conversation.get_absolute_url(),
                    priority=priority
                ))
            
            if notifications:
                Notification.objects.bulk_create(notifications, batch_size=100)
                
        except Exception as e:
            logger.error(f"Message notification error: {str(e)}")

@receiver(post_save, sender=GroupMessage)
def create_group_message_notification(sender, instance, created, **kwargs):
    if created:
        try:
            participants = instance.conversation.participants.exclude(
                id=instance.sender.id
            )
            notifications = [
                Notification(
                    user=user,
                    message=f"New message in {instance.conversation.name}",
                    notification_type="message",
                    content_object=instance,
                    url=f"/groups/{instance.conversation.id}/",
                )
                for user in participants
            ]
            if notifications:
                Notification.objects.bulk_create(notifications, batch_size=100)
                
        except Exception as e:
            logger.error(f"Error creating group message notification: {str(e)}")
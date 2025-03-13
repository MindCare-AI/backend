# users/signals.py
import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import CustomUser, PatientProfile, TherapistProfile, UserPreferences, UserSettings

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Signal handler to create related models when a user is created
    """
    if not created:
        return

    try:
        with transaction.atomic():
            # Create preferences and settings for all users
            UserPreferences.objects.get_or_create(user=instance)
            UserSettings.objects.get_or_create(user=instance)
            logger.info(f"Created preferences and settings for user: {instance.username}")

            # Create profile based on user type
            if instance.user_type == 'patient':
                PatientProfile.objects.get_or_create(user=instance)
                logger.info(f"Created patient profile for user {instance.username}")
            elif instance.user_type == 'therapist':
                TherapistProfile.objects.get_or_create(user=instance)
                logger.info(f"Created therapist profile for user {instance.username}")

    except Exception as e:
        logger.error(f"Error creating related models for user {instance.username}: {str(e)}", exc_info=True)
        raise

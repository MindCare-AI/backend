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
    Centralized signal handler to create all user-related models.
    Uses transactions for data consistency and includes error handling.
    """
    if not created:
        return

    try:
        with transaction.atomic():
            # Create profile based on user type
            if instance.user_type == "patient":
                # Check if PatientProfile already exists
                if not PatientProfile.objects.filter(user=instance).exists():
                    PatientProfile.objects.create(user=instance)
                    logger.info(f"Created patient profile for user {instance.username}")
            elif instance.user_type == "therapist":
                # Check if TherapistProfile already exists
                if not TherapistProfile.objects.filter(user=instance).exists():
                    TherapistProfile.objects.create(user=instance)
                    logger.info(f"Created therapist profile for user {instance.username}")

            # Check if UserPreferences already exists
            if not UserPreferences.objects.filter(user=instance).exists():
                UserPreferences.objects.create(user=instance)
                logger.info(f"Created preferences for user {instance.username}")

            # Check if UserSettings already exists
            if not UserSettings.objects.filter(user=instance).exists():
                UserSettings.objects.create(user=instance)
                logger.info(f"Created settings for user {instance.username}")

    except Exception as e:
        logger.error(f"Error creating related models for user {instance.username}: {str(e)}")
        raise

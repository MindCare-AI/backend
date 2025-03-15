# users/signals.py
import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import (
    CustomUser,
    UserPreferences,
    UserSettings,
)
from patient.models import PatientProfile
from therapist.models import TherapistProfile

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Signal handler to create or get associated models when a user is created/updated.
    Uses get_or_create to prevent duplicate entries.
    """
    try:
        with transaction.atomic():
            # Create or get preferences
            preferences, prefs_created = UserPreferences.objects.get_or_create(
                user=instance,
                defaults={
                    "dark_mode": False,
                    "language": "en",
                    "notification_preferences": {},
                },
            )
            if prefs_created:
                logger.info(f"Created preferences for user {instance.username}")

            # Create or get settings
            settings, settings_created = UserSettings.objects.get_or_create(
                user=instance,
                defaults={
                    "theme_preferences": {"mode": "system"},
                    "privacy_settings": {"profile_visibility": "public"},
                },
            )
            if settings_created:
                logger.info(f"Created settings for user {instance.username}")

    except Exception as e:
        logger.error(
            f"Error in create_user_related_models for {instance.username}: {str(e)}"
        )
        # Don't raise the exception here as it would prevent superuser creation
        # Just log the error and continue


@receiver(post_save, sender=User)
def update_user_jwt_claims(sender, instance, created, **kwargs):
    """
    Update JWT claims when user_type changes
    """
    if not created and instance.tracker.has_changed("user_type"):
        # Invalidate all existing tokens
        RefreshToken.for_user(instance)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create corresponding profile when user type is set
    """
    if not created and instance.tracker.has_changed("user_type"):
        try:
            if instance.user_type == "patient":
                PatientProfile.objects.get_or_create(user=instance)
            elif instance.user_type == "therapist":
                TherapistProfile.objects.get_or_create(user=instance)
        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")


@receiver(post_save, sender=get_user_model())
def create_user_preferences(sender, instance, created, **kwargs):
    """Create UserPreferences when a new user is created"""
    if created:
        try:
            UserPreferences.objects.create(user=instance)
            logger.info(f"Created preferences for user {instance.id}")
        except Exception as e:
            logger.error(f"Error creating preferences: {str(e)}")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_settings(sender, instance, created, **kwargs):
    """Create UserSettings when a new user is created."""
    if created:
        try:
            UserSettings.objects.create(
                user=instance,
                theme_preferences=settings.USER_SETTINGS.get(
                    "DEFAULT_THEME", {"mode": "system"}
                ),
                privacy_settings=settings.USER_SETTINGS.get(
                    "DEFAULT_PRIVACY", {"profile_visibility": "public"}
                ),
            )
            logger.info(f"Created settings for user {instance.id}")
        except Exception as e:
            logger.error(f"Error creating user settings: {str(e)}")

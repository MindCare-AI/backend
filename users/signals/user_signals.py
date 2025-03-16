# users/signals/user_signals.py
import logging
from django.db import transaction
from users.models.user import CustomUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from users.models.preferences import UserPreferences
from users.models.settings import UserSettings
from patient.models.patient_profile import PatientProfile

from therapist.models.therapist_profile import TherapistProfile
from django.apps import apps

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Creates or updates all related models for a user:
    - User preferences
    - User settings
    - User profile (patient/therapist)
    """
    try:
        with transaction.atomic():
            if created:
                # Create preferences
                preferences, _ = UserPreferences.objects.get_or_create(
                    user=instance,
                    defaults={
                        "dark_mode": False,
                        "language": settings.LANGUAGE_CODE,
                        "notification_preferences": {},
                    },
                )

                # Create settings
                settings_obj, _ = UserSettings.objects.get_or_create(
                    user=instance,
                    defaults={
                        "theme_preferences": settings.USER_SETTINGS.get(
                            "DEFAULT_THEME", {"mode": "system"}
                        ),
                        "privacy_settings": settings.USER_SETTINGS.get(
                            "DEFAULT_PRIVACY", {"profile_visibility": "public"}
                        ),
                    },
                )

            # Handle profile creation/updates based on user type
            if instance.user_type:
                if instance.user_type == "patient":
                    PatientProfile = apps.get_model("patient", "PatientProfile")
                    PatientProfile.objects.get_or_create(user=instance)
                elif instance.user_type == "therapist":
                    TherapistProfile = apps.get_model("therapist", "TherapistProfile")
                    TherapistProfile.objects.get_or_create(user=instance)

            # Handle JWT token refresh on user type change
            if not created and instance.tracker.has_changed("user_type"):
                RefreshToken.for_user(instance)

    except Exception as e:
        logger.error(
            f"Error handling user related models for {instance.username}: {str(e)}"
        )
        raise


@receiver(post_save, sender=User)
def update_user_jwt_claims(sender, instance, created, **kwargs):
    """Update JWT claims when user type changes"""
    if not created and instance.tracker.has_changed("user_type"):
        RefreshToken.for_user(instance)

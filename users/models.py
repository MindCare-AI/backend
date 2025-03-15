# users/models.py
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from model_utils import FieldTracker
from django.conf import settings
import json

logger = logging.getLogger(__name__)

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ("patient", "Patient"),
        ("therapist", "Therapist"),
    ]

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        blank=True,
        null=True,
        default="patient",
    )
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_mood_checkin = models.DateTimeField(blank=True, null=True)
    crisis_alert_enabled = models.BooleanField(default=True)
    passcode_enabled = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    tracker = FieldTracker(["user_type", "email", "phone_number", "crisis_alert_enabled"])

    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users_user"
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if not is_new and self.tracker.has_changed("user_type"):
            logger.info(
                f"User type changed from {self.tracker.previous('user_type')} to {self.user_type}"
            )

class UserPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    dark_mode = models.BooleanField(default=False)
    language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE
    )
    notification_preferences = models.JSONField(
        default=dict,
        blank=True
    )

    def get_notification_settings(self):
        settings = self.notification_preferences or {}
        return ", ".join(f"{k}: {v}" for k, v in settings.items())
    
    get_notification_settings.short_description = 'Notifications'

    class Meta:
        verbose_name_plural = "User preferences"
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username}'s Preferences"

class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    user_timezone = models.CharField(  # renamed from 'timezone'
        max_length=50,
        default=settings.TIME_ZONE
    )
    theme_preferences = models.JSONField(
        default=dict,
        help_text="Theme preferences as JSON object"
    )
    privacy_settings = models.JSONField(
        default=dict,
        help_text="Privacy settings as JSON object"
    )
    created_at = models.DateTimeField(default=timezone.now)  # now works as expected
    updated_at = models.DateTimeField(auto_now=True)

    def get_theme(self):
        return self.theme_preferences.get('mode', 'system')

    def get_privacy_level(self):
        return self.privacy_settings.get('profile_visibility', 'public')

    class Meta:
        verbose_name_plural = 'User settings'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Settings for {self.user.username}"

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to="profile_pics/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class PatientProfile(Profile):
    emergency_contact = models.JSONField(default=dict, blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)
    blood_type = models.CharField(max_length=3, blank=True, null=True)
    treatment_plan = models.TextField(blank=True, null=True)
    pain_level = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"

    def __str__(self):
        return f"{self.user.username}'s Patient Profile"

class TherapistProfile(Profile):
    specialization = models.CharField(max_length=100, blank=True, default="")
    license_number = models.CharField(max_length=50, blank=True, null=True)
    years_of_experience = models.IntegerField(default=0)
    treatment_approaches = models.JSONField(default=dict, blank=True, null=True)
    consultation_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    available_days = models.JSONField(default=dict, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)
    video_session_link = models.URLField(blank=True, null=True)
    languages_spoken = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Therapist Profile"
        verbose_name_plural = "Therapist Profiles"

    def __str__(self):
        return f"{self.user.username}'s Therapist Profile"

    def calculate_profile_completion(self):
        required_fields = [
            "bio",
            "profile_pic",
            "specialization",
            "license_number",
            "years_of_experience",
            "treatment_approaches",
            "consultation_fee",
            "available_days",
            "license_expiry",
            "video_session_link",
        ]

        completed = sum(1 for field in required_fields if getattr(self, field))
        return int((completed / len(required_fields)) * 100)

    @property
    def profile_completion_percentage(self):
        return self.calculate_profile_completion()

@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        with transaction.atomic():
            if instance.user_type == "patient":
                if not PatientProfile.objects.filter(user=instance).exists():
                    PatientProfile.objects.create(user=instance)
                    logger.info(f"Created patient profile for user {instance.username}")
            elif instance.user_type == "therapist":
                if not TherapistProfile.objects.filter(user=instance).exists():
                    TherapistProfile.objects.create(user=instance)
                    logger.info(f"Created therapist profile for user {instance.username}")

            if not UserPreferences.objects.filter(user=instance).exists():
                UserPreferences.objects.create(user=instance)
                logger.info(f"Created preferences for user {instance.username}")

            if not UserSettings.objects.filter(user=instance).exists():
                UserSettings.objects.create(user=instance)
                logger.info(f"Created settings for user {instance.username}")

    except Exception as e:
        logger.error(
            f"Error creating related models for user {instance.username}: {str(e)}"
        )
        raise

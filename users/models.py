# users/models.py
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from django.core.validators import MinValueValidator, MaxValueValidator

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ("patient", "Patient"),
        ("therapist", "Therapist"),
    )
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default="patient",
        help_text="Designates whether this user is a patient or therapist",
    )
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_mood_checkin = models.DateTimeField(blank=True, null=True)
    crisis_alert_enabled = models.BooleanField(default=True)
    passcode_enabled = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_user"
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username


class UserPreferences(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    language = models.CharField(max_length=10, default="en")
    notification_settings = models.JSONField(default=dict)
    theme = models.CharField(max_length=20, default="light")
    accessibility_settings = models.JSONField(default=dict)
    dark_mode = models.BooleanField(default=False)
    notification_preferences = models.JSONField(default=dict)

    class Meta:
        verbose_name_plural = "User preferences"

    def __str__(self):
        return f"Preferences of {self.user.username}"


class UserSettings(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, default="light")
    privacy_level = models.CharField(max_length=20, default="private")
    notifications = models.JSONField(default=dict)

    class Meta:
        verbose_name_plural = "User settings"

    def __str__(self):
        return f"Settings of {self.user.username}"


class PatientProfile(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A Positive'),
        ('A-', 'A Negative'),
        ('B+', 'B Positive'),
        ('B-', 'B Negative'),
        ('AB+', 'AB Positive'),
        ('AB-', 'AB Negative'),
        ('O+', 'O Positive'),
        ('O-', 'O Negative'),
    ]

    # Required Fields
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name="patient_profile_user"
    )

    # Optional Medical Information
    medical_history = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)
    blood_type = models.CharField(
        max_length=3, 
        choices=BLOOD_TYPE_CHOICES,
        blank=True, 
        null=True
    )
    treatment_plan = models.TextField(blank=True, null=True)
    pain_level = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], 
        blank=True, 
        null=True
    )

    # Optional Profile Info
    profile_pic = models.ImageField(
        upload_to="patient_profile_pics/%Y/%m/", 
        null=True, 
        blank=True
    )

    # Appointment Information
    last_appointment = models.DateTimeField(blank=True, null=True)
    next_appointment = models.DateTimeField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Patient Profiles"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s patient profile"


class TherapistProfile(models.Model):
    # Basic information - required
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name="therapist_profile_user"
    )
    
    # Core professional details - allow them to be optional initially
    specialization = models.CharField(max_length=100, blank=True, default="")
    license_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="License number format: AA-123456"
    )
    years_of_experience = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0
    )
    
    # Optional profile details
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(
        upload_to="therapist_profile_pics/", 
        null=True, 
        blank=True
    )

    # Professional fields - all optional for registration
    treatment_approaches = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Therapy methods and approaches used"
    )
    consultation_fee = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0.0, 
        validators=[MinValueValidator(0)]
    )
    available_days = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Weekly availability schedule"
    )
    license_expiry = models.DateField(blank=True, null=True)
    video_session_link = models.URLField(blank=True, null=True)
    languages_spoken = models.JSONField(
        default=list,
        blank=True,
        help_text="Languages the therapist can conduct sessions in"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Profile completion status
    is_profile_complete = models.BooleanField(default=False)
    profile_completion_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name_plural = "Therapist Profiles"

    def __str__(self):
        return f"{self.user.username}'s therapist profile"


@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Signal handler to create associated models when a new user is created.
    Uses transactions and existence checks to prevent duplicates.
    """
    if not created:
        return

    try:
        with transaction.atomic():
            # Create profile based on user type
            if instance.user_type == "patient":
                if not PatientProfile.objects.filter(user=instance).exists():
                    # Create with empty emergency contact dict
                    PatientProfile.objects.create(
                        user=instance
                    )
                    logger.info(f"Created patient profile for user {instance.username}")
            elif instance.user_type == "therapist":
                if not TherapistProfile.objects.filter(user=instance).exists():
                    TherapistProfile.objects.create(user=instance)
                    logger.info(
                        f"Created therapist profile for user {instance.username}"
                    )

            # Create preferences if they don't exist
            if not UserPreferences.objects.filter(user=instance).exists():
                UserPreferences.objects.create(user=instance)
                logger.info(f"Created preferences for user {instance.username}")

            # Create settings if they don't exist
            if not UserSettings.objects.filter(user=instance).exists():
                UserSettings.objects.create(user=instance)
                logger.info(f"Created settings for user {instance.username}")

    except Exception as e:
        logger.error(
            f"Error creating related models for user {instance.username}: {str(e)}"
        )
        raise

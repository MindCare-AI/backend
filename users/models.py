#users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericRelation


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_mood_checkin = models.DateTimeField(blank=True, null=True)  # Last mood tracking update
    crisis_alert_enabled = models.BooleanField(default=True)  # If user wants crisis alerts
    passcode_enabled = models.BooleanField(default=False)  # If user secures their app with a passcode
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users_user'
        verbose_name = 'user'  # Moved verbose_name here
        verbose_name_plural = 'users'  # Moved verbose_name_plural here
        ordering = ['-date_joined']

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)  # Make it nullable
    profile_pic = models.ImageField(
        upload_to='profile_pics/', 
        null=True, 
        blank=True
    )
    timezone = models.CharField(max_length=50, default='UTC')
    privacy_settings = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Optional privacy configuration"
    )
    stress_level = models.CharField(max_length=20, blank=True, null=True)  # Make it nullable
    wearable_data = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Optional wearable device data"
    )
    therapy_preferences = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Optional therapy preferences"
    )
    media_files = GenericRelation('media_handler.MediaFile')  # Add relation to MediaFile
    
    class Meta:
        verbose_name_plural = 'User profiles'

    def __str__(self):
        return f"{self.user.username}'s profile"


class UserPreferences(models.Model):
    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE)
    language = models.CharField(max_length=10, default='en')
    notification_settings = models.JSONField(default=dict)
    theme = models.CharField(max_length=20, default='light')  # Changed from theme_preference
    accessibility_settings = models.JSONField(default=dict)
    
    class Meta:
        verbose_name_plural = 'User preferences'

    def __str__(self):
        return f"Preferences of {self.user.username}"


class UserSettings(models.Model):
    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, default='light')
    privacy_level = models.CharField(max_length=20, default='private')
    notifications = models.JSONField(default=dict)  # This will store both email and push notifications
    
    class Meta:
        verbose_name_plural = 'User settings'

    def __str__(self):
        return f"Settings of {self.user.username}"


@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        UserPreferences.objects.create(user=instance)
        UserSettings.objects.create(user=instance)

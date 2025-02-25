from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'users_user'  # This sets the table name explicitly to 'users_user'

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.CharField(max_length=255, blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    privacy_settings = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class UserPreferences(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="preferences"
    )
    notification_settings = models.JSONField(blank=True, null=True)
    language = models.CharField(max_length=50, default="en")
    accessibility = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Preferences of {self.user.username}"


class UserSettings(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="settings"
    )
    theme = models.CharField(max_length=50, default="light")
    display_preferences = models.JSONField(blank=True, null=True)
    privacy_level = models.IntegerField(default=0)

    def __str__(self):
        return f"Settings of {self.user.username}"

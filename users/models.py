from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_set",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

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

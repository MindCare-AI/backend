from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone


# CustomUser model to extend Django's built-in User model
class CustomUser(AbstractUser):
    """Custom User model for extending the default Django User model."""
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Override to avoid reverse accessor clashes.
    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    def __str__(self):
        return self.username


# AuthToken model to store the user's authentication tokens
class AuthToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='auth_tokens')
    device_id = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"AuthToken for {self.user.username} on device {self.device_id}"


# UserDevice model to store user devices used for logging in
class UserDevice(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='devices')
    device_type = models.CharField(max_length=50)
    device_id = models.CharField(max_length=255)
    last_login = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.device_type} ({self.device_id}) for {self.user.username}"


# UserProfile model to store additional profile information
class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.CharField(max_length=255, blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    privacy_settings = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


# UserPreferences model for user preferences like notifications and language
class UserPreferences(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='preferences')
    notification_settings = models.JSONField(blank=True, null=True)
    language = models.CharField(max_length=50, default='en')
    accessibility = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Preferences of {self.user.username}"


# UserSettings model for user-specific settings like theme and privacy level
class UserSettings(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='settings')
    theme = models.CharField(max_length=50, default='light')
    display_preferences = models.JSONField(blank=True, null=True)
    privacy_level = models.IntegerField(default=0)

    def __str__(self):
        return f"Settings of {self.user.username}"

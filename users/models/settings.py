# users/models/settings.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings"
    )
    user_timezone = models.CharField(max_length=50, default=settings.TIME_ZONE)
    theme_preferences = models.JSONField(
        default=dict, help_text="Theme preferences as JSON object"
    )
    privacy_settings = models.JSONField(
        default=dict, help_text="Privacy settings as JSON object"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def get_theme(self):
        return self.theme_preferences.get("mode", "system")

    def get_privacy_level(self):
        return self.privacy_settings.get("profile_visibility", "public")

    class Meta:
        verbose_name_plural = "User settings"
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Settings for {self.user.username}"

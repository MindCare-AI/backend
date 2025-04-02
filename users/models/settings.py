# users/models/settings.py
from django.db import models
from django.conf import settings
import pytz


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings"
    )
    timezone = models.CharField(
        max_length=50, default="UTC", choices=[(tz, tz) for tz in pytz.common_timezones]
    )
    theme_preferences = models.JSONField(default=dict)
    privacy_settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self):
        return f"Settings for {self.user.username}"

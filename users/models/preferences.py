# users/models/preferences.py
from django.db import models
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class UserPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences"
    )
    dark_mode = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default="en")
    notification_preferences = models.JSONField(default=dict, blank=True)

    def get_notification_settings(self):
        config = self.notification_preferences or {}
        return ", ".join(f"{k}: {v}" for k, v in config.items())

    get_notification_settings.short_description = "Notifications"

    class Meta:
        verbose_name_plural = "User preferences"
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username}'s Preferences"

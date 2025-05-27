# users/models/preferences.py
from django.db import models
from django.conf import settings


class UserPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    # UI Preferences
    theme = models.CharField(
        max_length=20,
        choices=[("light", "Light"), ("dark", "Dark")],
        default="light",
    )
    dark_mode = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=50, default="UTC")

    # Notification Preferences
    notification_preferences = models.JSONField(default=dict)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_userpreferences"
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"Preferences for {self.user.username}"

    def save(self, *args, **kwargs):
        # Sync dark_mode with theme for backward compatibility
        if self.theme == "dark":
            self.dark_mode = True
        elif self.theme == "light":
            self.dark_mode = False
        super().save(*args, **kwargs)

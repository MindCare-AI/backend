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
    # Structured notification preferences instead of a JSON field:
    email_notifications = models.BooleanField(
        default=True,  # changed code
        help_text="Enable email notifications"
    )
    in_app_notifications = models.BooleanField(
        default=True,  # changed code
        help_text="Enable in-app notifications"
    )
    disabled_notification_types = models.ManyToManyField(
        "notifications.NotificationType", blank=True
    )

    def get_notification_settings(self):
        settings_list = [
            f"Email: {'enabled' if self.email_notifications else 'disabled'}",
            f"In-App: {'enabled' if self.in_app_notifications else 'disabled'}",
        ]
        disabled = list(
            self.disabled_notification_types.all().values_list("name", flat=True)
        )
        if disabled:
            settings_list.append("Disabled Types: " + ", ".join(disabled))
        return "; ".join(settings_list)

    get_notification_settings.short_description = "Notifications"

    def is_notification_allowed(self, notification_type, channel):
        """
        Check if a specific notification is allowed.
        :param notification_type: NotificationType instance.
        :param channel: 'email' or 'in_app'
        :return: bool
        """
        if channel == "email" and not self.email_notifications:
            return False
        if channel == "in_app" and not self.in_app_notifications:
            return False

        return not self.disabled_notification_types.filter(
            pk=notification_type.pk
        ).exists()

    def get_notification_preferences(self):
        """Structured format for API responses."""
        return {
            "email_enabled": self.email_notifications,
            "in_app_enabled": self.in_app_notifications,
            "disabled_types": list(
                self.disabled_notification_types.all().values_list("name", flat=True)
            ),
        }

    class Meta:
        verbose_name_plural = "User preferences"
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username}'s Preferences"

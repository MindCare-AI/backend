# notifications/models.py
from django.db import models
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.models import Group  # Import Group from auth

User = get_user_model()


class NotificationType(models.Model):
    """Core notification types for the platform"""

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    default_enabled = models.BooleanField(default=True)
    is_global = models.BooleanField(default=False)
    groups = models.ManyToManyField(
        Group,
        blank=True,
        help_text="User groups that can receive this notification type",
    )

    def __str__(self):
        return self.name


class Notification(models.Model):
    """User notifications"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.URLField(blank=True, null=True)
    priority = models.CharField(max_length=50)
    category = models.CharField(max_length=50, default="general")
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    email_sent = models.BooleanField(default=False)
    websocket_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["category"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["user", "category", "is_read"]),
            models.Index(fields=["notification_type", "created_at"]),
        ]

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()

    @classmethod
    def get_unread_count_by_category(cls, user):
        return (
            cls.objects.filter(user=user, is_read=False)
            .values("category")
            .annotate(count=Count("id"))
        )

    @classmethod
    def get_notifications_by_category(cls, user, category):
        return cls.objects.filter(
            user=user, category=category, is_archived=False
        ).order_by("-created_at")

    def __str__(self):
        return self.title


class NotificationPreference(models.Model):
    """User notification delivery preferences"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    disabled_notification_types = models.ManyToManyField(
        NotificationType,
        blank=True,
    )

    def __str__(self):
        return f"Preferences for {self.user.username}"

# notifications/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)


class NotificationType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    default_enabled = models.BooleanField(default=True)
    is_global = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_global"]),
            models.Index(fields=["default_enabled"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({'global' if self.is_global else 'user'})"


class Notification(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    read = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="medium"
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Generic foreign key for linking to various content types
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["read"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "read"]),
            models.Index(fields=["notification_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user}: {self.title}"

    def mark_read(self):
        """Mark notification as read with cache invalidation"""
        from django.core.cache import cache
        self.read = True
        self.save()
        # Invalidate relevant caches
        cache.delete(f'user_notifications_{self.user.id}')
        cache.delete(f'notification_count_{self.user.id}')

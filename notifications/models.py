# notifications/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ("message", "New Message"),
        ("appointment", "Appointment"),
        ("reminder", "Reminder"),
        ("system", "System Alert"),
        ("therapy_update", "Therapy Update"),
    )

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High')
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    notification_type = models.CharField(max_length=50)
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )
    url = models.URLField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # For generic relations to other objects
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['notification_type'])
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()

    def mark_as_unread(self):
        self.is_read = False
        self.save()

    def save(self, *args, **kwargs):
        if self.content_type and not self.object_id:
            raise ValidationError("object_id is required when content_type is set")
        if self.object_id and not self.content_type:
            raise ValidationError("content_type is required when object_id is set")
        super().save(*args, **kwargs)

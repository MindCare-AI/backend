#messaging/models/base.py
from django.db import models
from django.conf import settings

class BaseConversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name="%(class)s_conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True

class BaseMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)s_sent_messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name="%(class)s_read_messages",
        blank=True
    )
    
    class Meta:
        abstract = True
        ordering = ['-timestamp']
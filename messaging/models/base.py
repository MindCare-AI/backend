# messaging/models/base.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class BaseConversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="%(class)s_conversations",
        blank=True,  # Allow blank to prevent immediate validation issues
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)
    archive_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        # When the conversation exists (has a pk), ensure it has at least 2 participants.
        if self.pk and self.participants.count() < 2:
            raise ValidationError("Conversation must have at least 2 participants")

    def archive(self):
        """Archive the conversation"""
        self.archived = True
        self.archive_date = timezone.now()
        self.save()

    def unarchive(self):
        """Unarchive the conversation"""
        self.archived = False
        self.archive_date = None
        self.save()

    def __str__(self):
        return f"Conversation {self.pk}"


class BaseMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)s_sent_messages",
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="%(class)s_read_messages", blank=True
    )
    reactions = models.JSONField(default=dict)

    # New fields for message tracking
    edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_edited_messages",
    )
    edit_history = models.JSONField(default=list)  # Store previous versions

    # Soft deletion fields
    deleted = models.BooleanField(default=False)
    deletion_time = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_deleted_messages",
    )

    # Message metadata
    message_type = models.CharField(
        max_length=20,
        choices=[
            ("text", "Text Message"),
            ("image", "Image Message"),
            ("file", "File Attachment"),
            ("system", "System Message"),
        ],
        default="text",
    )
    metadata = models.JSONField(
        default=dict, help_text="Store additional message metadata"
    )

    class Meta:
        abstract = True
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["sender", "-timestamp"]),
            models.Index(fields=["message_type", "-timestamp"]),
        ]

    def soft_delete(self, deleted_by_user):
        """Soft delete a message"""
        try:
            self.deleted = True
            self.deletion_time = timezone.now()
            self.deleted_by = deleted_by_user
            self.save()

            logger.info(f"Message {self.id} soft deleted by user {deleted_by_user.id}")
            return True
        except Exception as e:
            logger.error(f"Error soft deleting message {self.id}: {str(e)}")
            return False

    def edit_message(self, new_content: str, edited_by_user):
        """Edit message content with version tracking"""
        try:
            # Create edit history entry
            MessageEditHistory.objects.create(
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.id,
                previous_content=self.content,
                edited_by=edited_by_user,
            )

            # Update message
            self.content = new_content
            self.edited = True
            self.edited_at = timezone.now()
            self.edited_by = edited_by_user
            self.save()

            logger.info(f"Message {self.id} edited by user {edited_by_user.id}")
            return True
        except Exception as e:
            logger.error(f"Error editing message {self.id}: {str(e)}")
            return False

    def add_reaction(self, user, reaction_type: str):
        """Add a reaction to the message"""
        if reaction_type not in self.reactions:
            self.reactions[reaction_type] = []

        if user.id not in self.reactions[reaction_type]:
            self.reactions[reaction_type].append(user.id)
            self.save()


class MessageEditHistory(models.Model):
    """Tracks edit history for any message type using a generic foreign key."""

    # Generic Foreign Key fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    message = GenericForeignKey("content_type", "object_id")

    # Edit history fields
    previous_content = models.TextField(help_text="The content before this edit")
    edited_at = models.DateTimeField(auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="message_edits",
    )

    class Meta:
        verbose_name = "Message Edit History"
        verbose_name_plural = "Message Edit Histories"
        ordering = ["-edited_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["edited_at"]),
        ]

    def __str__(self):
        return f"Edit by {self.edited_by} at {self.edited_at}"

    @property
    def edit_summary(self):
        """Returns a human-readable summary of the edit"""
        return {
            "editor": self.edited_by.get_full_name() or self.edited_by.username,
            "timestamp": self.edited_at,
            "previous_content": self.previous_content[:100] + "..."
            if len(self.previous_content) > 100
            else self.previous_content,
        }

# chatbot/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class ChatbotConversation(models.Model):
    """Enhanced model for storing chatbot conversations"""

    id = models.AutoField(primary_key=True)

    # User who owns this conversation
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_chatbot_conversations",
        help_text="The user who owns this conversation",
    )

    # Participants in the conversation (typically just the user)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="participated_chatbot_conversations",
        blank=True,
        help_text="Users participating in the conversation",
    )

    # Conversation details
    title = models.CharField(
        max_length=255, blank=True, help_text="Title of the conversation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True, help_text="Whether this conversation is active"
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional metadata for the conversation"
    )

    class Meta:
        verbose_name = "Chatbot Conversation"
        verbose_name_plural = "Chatbot Conversations"
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "-last_activity"]),
            models.Index(fields=["is_active", "-last_activity"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        title = self.title or f"Conversation {self.id}"
        return f"{title} - {self.user.username if self.user else 'Unknown User'}"

    def clean(self):
        """Validate the conversation"""
        super().clean()
        if self.title and len(self.title.strip()) == 0:
            raise ValidationError("Title cannot be empty or just whitespace")

    def save(self, *args, **kwargs):
        """Enhanced save method"""
        # Auto-generate title if not provided
        if not self.title:
            if self.id:
                self.title = f"Chat {self.id}"
            else:
                # For new conversations, use timestamp
                self.title = f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"

        # Clean the title
        if self.title:
            self.title = self.title.strip()

        self.full_clean()
        super().save(*args, **kwargs)

        # Add the user as a participant if not already added
        if self.user and not self.participants.filter(id=self.user.id).exists():
            self.participants.add(self.user)

    def get_message_count(self):
        """Get the number of messages in this conversation"""
        return self.messages.count()

    def get_last_message(self):
        """Get the last message in this conversation"""
        return self.messages.order_by("-timestamp").first()

    def mark_as_inactive(self):
        """Mark this conversation as inactive (archive it)"""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def mark_as_active(self):
        """Mark this conversation as active (unarchive it)"""
        self.is_active = True
        self.save(update_fields=["is_active"])


class ChatMessage(models.Model):
    """Enhanced model for individual chat messages"""

    MESSAGE_TYPE_CHOICES = (
        ("text", "Text"),
        ("system", "System Message"),
        ("error", "Error Message"),
    )

    id = models.AutoField(primary_key=True)

    # Relationship to conversation
    conversation = models.ForeignKey(
        ChatbotConversation, on_delete=models.CASCADE, related_name="messages"
    )

    # Message content and metadata
    content = models.TextField()
    is_bot = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(
        max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text"
    )

    # Sender (null for bot messages)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )

    # Message relationships
    parent_message = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
    )

    # Additional data
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["conversation", "timestamp"]),
            models.Index(fields=["is_bot", "timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self):
        sender = (
            "Bot"
            if self.is_bot
            else (self.sender.username if self.sender else "Unknown")
        )
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"{sender}: {content_preview}"

    def clean(self):
        """Validate the message"""
        super().clean()
        if not self.content or len(self.content.strip()) == 0:
            raise ValidationError("Message content cannot be empty")

    def save(self, *args, **kwargs):
        """Enhanced save method"""
        self.full_clean()
        super().save(*args, **kwargs)

        # Update conversation's last activity
        if self.conversation:
            self.conversation.last_activity = self.timestamp
            self.conversation.save(update_fields=["last_activity"])

    def is_from_user(self, user):
        """Check if this message is from a specific user"""
        return self.sender == user

    def get_response_count(self):
        """Get the number of responses to this message"""
        return self.responses.count()


class ConversationSummary(models.Model):
    """Enhanced model for conversation summaries"""

    id = models.UUIDField(
        primary_key=True, default=models.UUIDField().default, editable=False
    )

    # Conversation reference
    conversation_id = models.CharField(
        max_length=255, help_text="ID of the conversation"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_summaries",
    )

    # Summary metadata
    created_at = models.DateTimeField(auto_now_add=True)

    # Message range for this summary
    start_message = models.ForeignKey(
        ChatMessage, on_delete=models.SET_NULL, null=True, related_name="summary_starts"
    )
    end_message = models.ForeignKey(
        ChatMessage, on_delete=models.SET_NULL, null=True, related_name="summary_ends"
    )

    # Summary content
    summary_text = models.TextField()
    key_points = models.JSONField(default=list)
    emotional_context = models.JSONField(default=dict)
    message_count = models.IntegerField(default=0)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Conversation Summary"
        verbose_name_plural = "Conversation Summaries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation_id", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Summary for conversation {self.conversation_id} ({self.message_count} messages)"

    def clean(self):
        """Validate the summary"""
        super().clean()
        if not self.summary_text or len(self.summary_text.strip()) == 0:
            raise ValidationError("Summary text cannot be empty")

    def save(self, *args, **kwargs):
        """Enhanced save method"""
        self.full_clean()
        super().save(*args, **kwargs)

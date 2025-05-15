# chatbot/models.py
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class ChatbotConversation(models.Model):
    """Model for storing chatbot conversations"""

    id = models.AutoField(primary_key=True)  # now using normal int instead of UUID
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_chatbot_conversations",  # Unique related_name
        help_text="The user who owns this conversation",
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional metadata for the conversation"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="participated_chatbot_conversations",  # Unique related_name
        blank=True,
        help_text="Users participating in the conversation",
    )

    class Meta:
        ordering = ["-last_activity"]
        verbose_name = "Chatbot Conversation"
        verbose_name_plural = "Chatbot Conversations"

    def __str__(self):
        return f"{self.title} ({self.user})"


class ChatMessage(models.Model):
    """Model for storing individual chat messages"""

    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        ChatbotConversation, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField()
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )
    is_bot = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(
        max_length=20,
        choices=[
            ("text", "Text"),
            ("system", "System Message"),
            ("error", "Error Message"),
        ],
        default="text",
    )
    metadata = models.JSONField(default=dict, blank=True)
    parent_message = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responses",
    )

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["conversation", "timestamp"]),
        ]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    def __str__(self):
        return f"Message {self.id} in {self.conversation}"

    def clean(self):
        if not self.is_bot and not self.sender:
            raise ValidationError("User messages must have a sender")
        if self.is_bot and self.sender:
            raise ValidationError("Bot messages should not have a sender")


class ConversationSummary(models.Model):
    """Model for storing conversation summaries"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        ChatbotConversation, on_delete=models.CASCADE, related_name="summaries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    summary_text = models.TextField()
    key_points = models.JSONField(default=list)
    emotional_context = models.JSONField(default=dict)
    start_message = models.ForeignKey(
        ChatMessage, on_delete=models.SET_NULL, null=True, related_name="summary_starts"
    )
    end_message = models.ForeignKey(
        ChatMessage, on_delete=models.SET_NULL, null=True, related_name="summary_ends"
    )
    message_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Conversation Summary"
        verbose_name_plural = "Conversation Summaries"

    def __str__(self):
        return f"Summary for conversation {self.conversation.id} ({self.created_at.strftime('%Y-%m-%d')})"

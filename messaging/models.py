#messaging/models.py
from django.db import models
from django.conf import settings


class ConversationType(models.TextChoices):
    DIRECT = "direct", "Direct Message"
    GROUP = "group", "Group Chat"
    CHATBOT = "chatbot", "Chatbot Conversation"


class MessageType(models.TextChoices):
    TEXT = "text", "Text"
    SYSTEM = "system", "System"
    ACTION = "action", "Action"


class ContentType(models.TextChoices):
    TEXT = "text", "Plain Text"
    MARKDOWN = "markdown", "Markdown"
    RICH_TEXT = "rich_text", "Rich Text"


class Conversation(models.Model):
    conversation_type = models.CharField(
        max_length=20, choices=ConversationType.choices, default=ConversationType.DIRECT
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="conversations"
    )
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="moderated_conversations", blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.ForeignKey(
        "Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    group_name = models.CharField(max_length=100, blank=True, null=True)
    group_description = models.TextField(blank=True, null=True)

    def update_last_message(self):
        self.last_message = self.messages.order_by("-timestamp").first()
        self.save()

    def __str__(self):
        if self.conversation_type == ConversationType.DIRECT:
            return f"Direct Chat #{self.id}"
        elif self.conversation_type == ConversationType.GROUP:
            return f"Group Chat: {self.group_name}"
        else:
            return f"Chatbot Conversation #{self.id}"

    class Meta:
        indexes = [
            models.Index(fields=["conversation_type"]),
        ]


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_chatbot = models.BooleanField(default=False)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="read_messages", blank=True
    )
    message_type = models.CharField(
        max_length=10, choices=MessageType.choices, default=MessageType.TEXT
    )
    content_type = models.CharField(
        max_length=20, choices=ContentType.choices, default=ContentType.TEXT
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["conversation", "timestamp"]),
            models.Index(fields=["sender", "timestamp"]),
            models.Index(fields=["message_type"]),
        ]

    def __str__(self):
        return f"Message #{self.id} in {self.conversation}"

    def mark_read(self, user):
        self.read_by.add(user)


class Reaction(models.Model):
    message = models.ForeignKey(
        Message, related_name="reactions", on_delete=models.CASCADE
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user", "emoji")
        indexes = [
            models.Index(fields=["message", "emoji"]),
            models.Index(fields=["user", "emoji"]),
        ]

    def __str__(self):
        return f"{self.user.username} reacted with {self.emoji} to message #{self.message.id}"

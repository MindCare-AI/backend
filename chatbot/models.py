from django.db import models
from django.conf import settings

class ChatbotConversation(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_chatbot_conversation",  # Changed from chatbot_conversation
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Chatbot conversation with {self.user.username}"


class ChatbotMessage(models.Model):
    conversation = models.ForeignKey(
        ChatbotConversation, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_bot = models.BooleanField(default=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_chatbot_sent_messages",  # Changed from chatbot_sent_messages
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{'Bot' if self.is_bot else 'User'} message in conversation {self.conversation_id}"

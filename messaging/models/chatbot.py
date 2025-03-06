# messaging/models/chatbot.py
from django.db import models
from django.conf import settings
from .base import BaseMessage

class ChatbotConversation(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chatbot_conversation'
    )
    created_at = models.DateTimeField(auto_now_add=True)

class ChatbotMessage(BaseMessage):
    conversation = models.ForeignKey(
        ChatbotConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    is_bot = models.BooleanField(default=False)
    
    # Override sender to allow null for bot messages
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chatbot_sent_messages'
    )

# messaging/models/one_to_one.py
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from .base import BaseConversation, BaseMessage

class OneToOneConversationParticipant(models.Model):
    conversation = models.ForeignKey('OneToOneConversation', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('conversation', 'user'),)
        db_table = 'messaging_onetooneconversation_participants'


class OneToOneConversation(BaseConversation):
    # Override the inherited participants field with an explicit through model.
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='OneToOneConversationParticipant',
        related_name="onetoone_conversations"
    )
    
    class Meta:
        verbose_name = "One-to-One Conversation"
        verbose_name_plural = "One-to-One Conversations"
    
    def clean(self):
        super().clean()
        if self.participants.count() != 2:
            raise ValidationError("One-to-one conversations must have exactly 2 participants")


class OneToOneMessage(BaseMessage):
    conversation = models.ForeignKey(
        OneToOneConversation, on_delete=models.CASCADE, related_name="messages"
    )

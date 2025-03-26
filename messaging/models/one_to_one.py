# messaging/models/one_to_one.py
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from .base import BaseConversation, BaseMessage
from django.contrib.postgres.fields import ArrayField


class OneToOneConversationParticipant(models.Model):
    conversation = models.ForeignKey("OneToOneConversation", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = (("conversation", "user"),)


class OneToOneConversation(BaseConversation):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="OneToOneConversationParticipant",
        related_name="onetoone_conversations",
    )

    class Meta:
        verbose_name = "One-to-One Conversation"
        verbose_name_plural = "One-to-One Conversations"

    def clean(self):
        super().clean()
        if self.pk and self.participants.count() != 2:
            raise ValidationError("One-to-one conversations must have exactly 2 participants.")


@receiver(m2m_changed, sender=OneToOneConversation.participants.through)
def validate_one_to_one_participants(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        if instance.pk and instance.participants.count() != 2:
            raise ValidationError("One-to-one conversations must have exactly 2 participants.")


class OneToOneMessage(BaseMessage):
    conversation = models.ForeignKey(
        OneToOneConversation, on_delete=models.CASCADE, related_name="messages"
    )
    edit_history = ArrayField(
        models.JSONField(),
        default=list,
        blank=True,
        help_text="History of message edits"
    )

# messaging/models/one_to_one.py
from django.db import models
from django.conf import settings
from .base import BaseConversation, BaseMessage

class OneToOneConversation(BaseConversation):
    # Removed unique_together and custom save logic.
    # Enforce exactly two participants in the serializer or view.
    pass

class OneToOneMessage(BaseMessage):
    conversation = models.ForeignKey(
        OneToOneConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

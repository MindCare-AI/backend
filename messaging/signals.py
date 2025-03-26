# messaging/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models.one_to_one import OneToOneMessage
from .models.group import GroupMessage
from .models.chatbot import ChatbotMessage

@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
@receiver(post_save, sender=ChatbotMessage)
@receiver(post_delete, sender=OneToOneMessage)
@receiver(post_delete, sender=GroupMessage)
@receiver(post_delete, sender=ChatbotMessage)
def update_conversation_on_message_change(sender, instance, **kwargs):
    conversation = instance.conversation
    conversation.last_activity = timezone.now()
    conversation.save()

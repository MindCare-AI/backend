# messaging/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import OneToOneMessage, GroupMessage, ChatbotMessage

@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
@receiver(post_save, sender=ChatbotMessage)
def update_conversation_activity(sender, instance, **kwargs):
    conversation = instance.conversation
    conversation.last_activity = timezone.now()
    conversation.save()

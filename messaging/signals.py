# messaging/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message


@receiver(post_save, sender=Message)
def update_conversation(sender, instance, **kwargs):
    instance.conversation.update_last_message()

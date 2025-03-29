# messaging/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import logging

# Add new imports for WebSocket updates
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models.one_to_one import OneToOneMessage
from .models.group import GroupMessage
from .models.chatbot import ChatbotMessage
from .models.base import BaseMessage

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=OneToOneMessage)
@receiver(post_delete, sender=GroupMessage)
@receiver(post_delete, sender=ChatbotMessage)
def update_conversation_on_message_change_delete(sender, instance, **kwargs):
    conversation = instance.conversation
    conversation.last_activity = timezone.now()
    conversation.save()


@receiver(pre_save, sender=BaseMessage)
def handle_message_edit(sender, instance, **kwargs):
    """Handle message edit tracking"""
    try:
        if instance.pk:  # Only for existing messages
            old_instance = sender.objects.get(pk=instance.pk)

            # Check if content changed
            if old_instance.content != instance.content:
                # Clear cache
                cache_key = f"message_edit_history_{instance.id}"
                cache.delete(cache_key)

                # Log edit
                logger.info(
                    f"Message {instance.id} edited by {instance.edited_by}"
                    f" at {instance.edited_at}"
                )

    except Exception as e:
        logger.error(f"Error handling message edit: {str(e)}", exc_info=True)


@receiver(post_save, sender=BaseMessage)
def handle_message_reaction(sender, instance, created, **kwargs):
    """Handle reaction caching"""
    try:
        if not created and hasattr(instance, "reactions"):
            # Update reactions cache
            cache_key = f"message_reactions_{instance.id}"
            cache.set(cache_key, instance.reactions, timeout=3600)

    except Exception as e:
        logger.error(f"Error handling message reaction: {str(e)}", exc_info=True)

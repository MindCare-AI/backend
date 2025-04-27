# messaging/caches/signal_handlers.py
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from ..models.base import BaseMessage
from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation
from ..models.chatbot import ChatbotMessage, ChatbotConversation
from .cache_manager import message_cache

logger = logging.getLogger(__name__)

# ===== Message Signals =====

@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
@receiver(post_save, sender=ChatbotMessage)
def cache_message_on_save(sender, instance, created, **kwargs):
    """Cache a message when it's created or updated."""
    try:
        # Cache the message
        message_cache.cache_message(instance)
        
        # Update conversation last activity
        conversation = instance.conversation
        conversation.last_activity = timezone.now()
        conversation.save(update_fields=['last_activity'])
        
        # Cache the conversation
        message_cache.cache_conversation(conversation)
        
        logger.debug(f"Message {instance.id} cached {'(created)' if created else '(updated)'}")
    except Exception as e:
        logger.error(f"Error caching message {instance.id}: {str(e)}", exc_info=True)


@receiver(pre_save, sender=OneToOneMessage)
@receiver(pre_save, sender=GroupMessage)
@receiver(pre_save, sender=ChatbotMessage)
def handle_message_edit_cache(sender, instance, **kwargs):
    """Prepare message edit history for caching."""
    try:
        # Only for existing messages
        if not instance.pk:
            return
            
        # Store the original message for later use
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            
            # If content changed, add to edit history
            if old_instance.content != instance.content:
                instance._content_changed = True
                instance._original_content = old_instance.content

            # Track reaction changes
            if hasattr(old_instance, 'reactions') and hasattr(instance, 'reactions') and old_instance.reactions != instance.reactions:
                instance._reactions_changed = True
                
        except sender.DoesNotExist:
            pass
    except Exception as e:
        logger.error(f"Error in pre-save message edit cache: {str(e)}", exc_info=True)


@receiver(post_delete, sender=OneToOneMessage)
@receiver(post_delete, sender=GroupMessage)
@receiver(post_delete, sender=ChatbotMessage) 
def invalidate_message_cache(sender, instance, **kwargs):
    """Remove a message from cache when it's deleted."""
    try:
        # Invalidate message in cache
        message_cache.invalidate_message(instance.id)
        
        # Update conversation last activity
        conversation = instance.conversation
        conversation.last_activity = timezone.now()
        conversation.save(update_fields=['last_activity'])
        
        # Cache the updated conversation
        message_cache.cache_conversation(conversation)
        
        logger.debug(f"Message {instance.id} removed from cache")
    except Exception as e:
        logger.error(f"Error invalidating message cache for {instance.id}: {str(e)}", exc_info=True)


# ===== Conversation Signals =====

@receiver(post_save, sender=OneToOneConversation)
@receiver(post_save, sender=GroupConversation)
@receiver(post_save, sender=ChatbotConversation)
def cache_conversation_on_save(sender, instance, created, **kwargs):
    """Cache a conversation when it's created or updated."""
    try:
        # Cache the conversation
        message_cache.cache_conversation(instance)
        
        if created:
            # For new conversations, update user conversation lists
            for participant in instance.participants.all():
                message_cache._add_to_user_conversations(participant.id, instance.id)
        
        logger.debug(f"Conversation {instance.id} cached {'(created)' if created else '(updated)'}")
    except Exception as e:
        logger.error(f"Error caching conversation {instance.id}: {str(e)}", exc_info=True)


@receiver(post_delete, sender=OneToOneConversation)
@receiver(post_delete, sender=GroupConversation)
@receiver(post_delete, sender=ChatbotConversation)
def cleanup_conversation_cache(sender, instance, **kwargs):
    """Clean up cache when a conversation is deleted."""
    try:
        # Clear conversation from cache
        conversation_key = f"{message_cache.CONVERSATION_PREFIX}{instance.id}"
        message_cache.cache.delete(conversation_key)
        
        # Clear message batch cache
        batch_key = f"{message_cache.MESSAGE_BATCH_PREFIX}{instance.id}"
        message_cache.cache.delete(batch_key)
        
        # Remove from user conversation lists
        for participant in instance.participants.all():
            user_convs_key = f"{message_cache.USER_CONVERSATIONS_PREFIX}{participant.id}"
            conversation_ids = message_cache.cache.get(user_convs_key, [])
            if instance.id in conversation_ids:
                conversation_ids.remove(instance.id)
                message_cache.cache.set(user_convs_key, conversation_ids, message_cache.CONVERSATION_LIST_TIMEOUT)
        
        logger.debug(f"Conversation {instance.id} removed from cache")
    except Exception as e:
        logger.error(f"Error cleaning up cache for conversation {instance.id}: {str(e)}", exc_info=True)
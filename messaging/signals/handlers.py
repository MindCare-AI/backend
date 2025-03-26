from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from ..models.base import BaseMessage
from ..services.notifications import UnifiedNotificationService
import logging

logger = logging.getLogger(__name__)

@receiver([pre_save], sender=BaseMessage)
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

@receiver([post_save], sender=BaseMessage)
def handle_message_reaction(sender, instance, created, **kwargs):
    """Handle reaction notifications and caching"""
    try:
        if not created and instance.reactions_changed:
            # Get the user who added/changed the reaction
            reactor = instance.last_reactor
            
            # Skip if no reactor (happens during reaction removal)
            if not reactor:
                return
                
            # Notify message sender if different from reactor
            if reactor != instance.sender:
                notification_service = UnifiedNotificationService()
                notification_service.send_notification(
                    user=instance.sender,
                    notification_type_name="message_reaction",
                    title="New Reaction",
                    message=f"{reactor.get_full_name()} reacted to your message",
                    metadata={
                        "message_id": str(instance.id),
                        "conversation_id": str(instance.conversation.id),
                        "reactor_id": str(reactor.id),
                        "reaction_type": instance.last_reaction_type,
                        "message_preview": instance.content[:100],
                    },
                    send_email=False,
                    send_in_app=True,
                    priority="low"
                )
            
            # Update reactions cache
            cache_key = f"message_reactions_{instance.id}"
            cache.set(cache_key, instance.reactions, timeout=3600)
            
    except Exception as e:
        logger.error(f"Error handling message reaction: {str(e)}", exc_info=True)
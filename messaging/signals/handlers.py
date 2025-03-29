# messaging/signals/handlers.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from ..models.base import BaseMessage
from ..models.one_to_one import OneToOneMessage
from ..models.group import GroupMessage
from ..models.chatbot import ChatbotMessage
from notifications.services import UnifiedNotificationService
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

            # Check if reactions changed
            if old_instance.reactions != instance.reactions:
                # Set a flag for post_save handlers to use
                instance._reactions_changed = True

                # Preserve last_reactor info for notifications if not already set
                if (
                    not hasattr(instance, "_last_reactor")
                    or instance._last_reactor is None
                ):
                    instance._last_reactor = getattr(instance, "last_reactor", None)

                logger.debug(f"Reactions changed for message {instance.id}")

    except Exception as e:
        logger.error(f"Error handling message edit: {str(e)}", exc_info=True)


@receiver([post_save], sender=BaseMessage)
def handle_message_reaction(sender, instance, created, **kwargs):
    """Handle reaction notifications and caching"""
    try:
        # Check if reactions changed using our flag from pre_save
        if not created and getattr(instance, "_reactions_changed", False):
            # Get the user who added/changed the reaction
            reactor = getattr(instance, "_last_reactor", None)

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
                        "reaction_type": getattr(
                            instance, "last_reaction_type", "unknown"
                        ),
                        "message_preview": instance.content[:100],
                    },
                    send_email=False,
                    send_in_app=True,
                    priority="low",
                )

            # Update reactions cache
            cache_key = f"message_reactions_{instance.id}"
            cache.set(cache_key, instance.reactions, timeout=3600)

    except Exception as e:
        logger.error(f"Error handling message reaction: {str(e)}", exc_info=True)


@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
@receiver(post_save, sender=ChatbotMessage)
def update_conversation_on_message_change(sender, instance, created, **kwargs):
    conversation = instance.conversation
    conversation.last_activity = timezone.now()
    conversation.save()

    # Send WebSocket update only for new messages or edited messages
    if created or getattr(instance, "edited", False):
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.error("Channel layer not available")
                return

            event_type = "message_create" if created else "message_update"

            message_data = {
                "type": "conversation_message",  # Match the consumer method name
                "message": {
                    "event_type": event_type,
                    "id": str(instance.id),
                    "content": instance.content,
                    "sender_id": str(instance.sender.id) if instance.sender else None,
                    "sender_name": instance.sender.username
                    if instance.sender
                    else "System",
                    "timestamp": instance.timestamp.isoformat(),
                    "conversation_id": str(conversation.id),
                    "message_type": getattr(instance, "message_type", "text"),
                    "is_edited": getattr(instance, "edited", False),
                },
            }

            async_to_sync(channel_layer.group_send)(
                f"conversation_{conversation.id}", message_data
            )

            logger.debug(f"Sent WebSocket {event_type} for message {instance.id}")

        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}", exc_info=True)


@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
def broadcast_message(sender, instance, created, **kwargs):
    if created:  # Only for new messages
        try:
            channel_layer = get_channel_layer()
            conversation_id = str(instance.conversation.id)

            # Enhanced message data
            message_data = {
                "type": "conversation_message",
                "message": {
                    "id": str(instance.id),
                    "content": instance.content,
                    "sender_id": str(instance.sender.id),
                    "sender_name": instance.sender.username,
                    "conversation_id": conversation_id,
                    "timestamp": instance.timestamp.isoformat(),
                    "event_type": "new_message",
                    "read_by": [],  # Initialize empty read receipts
                    "message_type": getattr(instance, "message_type", "text"),
                },
            }

            # Broadcast to the conversation group
            async_to_sync(channel_layer.group_send)(
                f"conversation_{conversation_id}", message_data
            )

            logger.debug(
                f"Broadcasting new message {instance.id} to conversation {conversation_id}"
            )

        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}", exc_info=True)

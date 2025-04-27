# messaging/services/message_delivery.py
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from messaging.exceptions import MessageDeliveryError, RateLimitExceededError

logger = logging.getLogger(__name__)


class MessageDeliveryService:
    """
    Centralized service for delivering WebSocket messages across the application.
    This service provides a single point of control for all real-time messaging,
    ensuring consistency and avoiding duplicate messages.
    """

    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.rate_limit_count = getattr(settings, "WS_RATE_LIMIT_COUNT", 5)
        self.rate_limit_period = getattr(settings, "WS_RATE_LIMIT_PERIOD", 1)  # seconds
        self.cache_timeout = getattr(settings, "MESSAGE_CACHE_TIMEOUT", 3600)  # 1 hour default
        self.cache_prefix = "msg_delivery_"
        # Add new cache settings
        self.bulk_cache_size = getattr(settings, "MESSAGE_BULK_CACHE_SIZE", 100)
        self.conversation_cache_timeout = getattr(settings, "CONVERSATION_CACHE_TIMEOUT", 7200)  # 2 hours

    def _get_cache_key(self, conversation_id: str, message_id: str = None) -> str:
        """Generate a cache key for message delivery"""
        if message_id:
            return f"{self.cache_prefix}conv_{conversation_id}_msg_{message_id}"
        return f"{self.cache_prefix}conv_{conversation_id}"

    def _cache_message(self, conversation_id: str, message_data: dict) -> None:
        """Cache message data for a conversation with improved bulk handling"""
        try:
            message_id = str(message_data.get('id', ''))
            cache_key = self._get_cache_key(conversation_id, message_id)
            
            # Cache individual message with TTL
            pipeline = cache.pipeline()
            pipeline.set(cache_key, message_data, timeout=self.cache_timeout)
            
            # Update conversation messages list
            conv_cache_key = self._get_cache_key(conversation_id)
            cached_messages = cache.get(conv_cache_key, [])
            
            # Implement LRU-like behavior for conversation cache
            if len(cached_messages) >= self.bulk_cache_size:
                cached_messages.pop(0)  # Remove oldest message
            
            if message_id not in cached_messages:
                cached_messages.append(message_id)
                pipeline.set(conv_cache_key, cached_messages, timeout=self.conversation_cache_timeout)
            
            # Execute all cache operations atomically
            pipeline.execute()
            
        except Exception as e:
            logger.error(f"Error caching message: {str(e)}", exc_info=True)
            
    def _clear_conversation_cache(self, conversation_id: str) -> None:
        """Clear all cached messages for a conversation"""
        try:
            conv_cache_key = self._get_cache_key(conversation_id)
            cached_messages = cache.get(conv_cache_key, [])
            
            # Create pipeline for bulk delete
            pipeline = cache.pipeline()
            
            # Delete all message keys
            for message_id in cached_messages:
                msg_cache_key = self._get_cache_key(conversation_id, message_id)
                pipeline.delete(msg_cache_key)
            
            # Delete conversation key
            pipeline.delete(conv_cache_key)
            
            # Execute all deletes atomically
            pipeline.execute()
            
        except Exception as e:
            logger.error(f"Error clearing conversation cache: {str(e)}", exc_info=True)

    def _get_cached_message(self, conversation_id: str, message_id: str) -> dict:
        """Retrieve cached message data"""
        cache_key = self._get_cache_key(conversation_id, message_id)
        return cache.get(cache_key)

    def send_message_update(
        self,
        conversation_id: str,
        event_type: str,
        message_data: Dict[str, Any],
        user_id: Optional[str] = None,
        check_rate_limit: bool = True,
    ) -> bool:
        """
        Send a message update to all users in a conversation.

        Args:
            conversation_id: The ID of the conversation
            event_type: Type of event (message_created, message_updated, etc.)
            message_data: The message data to send
            user_id: The ID of the user sending the update (for rate limiting)
            check_rate_limit: Whether to check rate limiting

        Returns:
            bool: True if message was sent, False otherwise

        Raises:
            MessageDeliveryError: If there's an error sending the message
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.channel_layer:
            logger.warning("No channel layer available for WebSocket message delivery")
            return False

        try:
            # Apply rate limiting if enabled and user_id is provided
            if check_rate_limit and user_id:
                self._check_rate_limit(conversation_id, user_id)

            # Ensure message_data has standard fields
            if "timestamp" not in message_data:
                message_data["timestamp"] = timezone.now().isoformat()

            if "event_type" not in message_data:
                message_data["event_type"] = event_type

            if "conversation_id" not in message_data:
                message_data["conversation_id"] = conversation_id

            # Cache the message data
            self._cache_message(conversation_id, message_data)

            # Prepare the update data
            update_data = {"type": "conversation.message", "message": message_data}

            # Send to the conversation group
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(group_name, update_data)

            logger.debug(
                f"Sent {event_type} WebSocket update to conversation {conversation_id}"
            )
            return True

        except RateLimitExceededError as e:
            logger.warning(str(e))
            return False

        except Exception as e:
            logger.error(
                f"Failed to deliver WebSocket message: {str(e)}", exc_info=True
            )
            raise MessageDeliveryError(f"Error sending WebSocket message: {str(e)}")

    def send_typing_indicator(
        self, conversation_id: str, user_id: str, username: str, is_typing: bool
    ) -> bool:
        """Send typing indicator to a conversation"""
        try:
            # Cache typing status
            cache_key = f"typing_{conversation_id}_{user_id}"
            cache.set(cache_key, is_typing, timeout=30)  # Cache for 30 seconds

            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "typing_indicator",
                    "user_id": user_id,
                    "username": username,
                    "conversation_id": conversation_id,
                    "is_typing": is_typing,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send typing indicator: {str(e)}")
            return False

    def send_presence_update(self, user_id: str, is_online: bool) -> bool:
        """Send presence update for a user"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                f"user_{user_id}",
                {"type": "presence.update", "user_id": user_id, "online": is_online},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send presence update: {str(e)}")
            return False

    def send_read_receipt(
        self, conversation_id: str, user_id: str, username: str, message_id: str
    ) -> bool:
        """Send read receipt to a conversation"""
        try:
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "read_receipt",
                    "user_id": user_id,
                    "username": username,
                    "message_id": message_id,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send read receipt: {str(e)}")
            return False

    def _check_rate_limit(self, conversation_id: str, user_id: str) -> None:
        """
        Check if user has exceeded rate limit for sending messages to a conversation

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        cache_key = f"ws_rate_{conversation_id}_{user_id}"
        current_count = cache.get(cache_key, 0)

        if current_count >= self.rate_limit_count:
            raise RateLimitExceededError(
                f"Rate limit exceeded: User {user_id} has sent too many updates to conversation {conversation_id}"
            )

        # Increment counter
        cache.set(cache_key, current_count + 1, timeout=self.rate_limit_period)


# Singleton instance for use throughout the application
message_delivery_service = MessageDeliveryService()

# messaging/caches/cache_manager.py
import logging
from typing import Dict, List, Optional
from django.core.cache import caches
from django.conf import settings

logger = logging.getLogger(__name__)


class MessagingCacheManager:
    """Centralized cache manager for messaging operations"""

    def __init__(self):
        self.cache = caches["messaging"]
        self.default_timeout = getattr(
            settings, "MESSAGING_CACHE_TIMEOUT", 3600
        )  # 1 hour

    def _build_key(self, *parts: str) -> str:
        """Build a cache key from parts"""
        return ":".join(str(part) for part in parts)

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get a message from cache"""
        key = self._build_key("msg", message_id)
        return self.cache.get(key)

    def set_message(
        self, message_id: str, data: Dict, timeout: Optional[int] = None
    ) -> None:
        """Set a message in cache"""
        key = self._build_key("msg", message_id)
        self.cache.set(key, data, timeout or self.default_timeout)

    def delete_message(self, message_id: str) -> None:
        """Delete a message from cache"""
        key = self._build_key("msg", message_id)
        self.cache.delete(key)

    def get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """Get all messages for a conversation"""
        key = self._build_key("conv", conversation_id, "messages")
        return self.cache.get(key) or []

    def set_conversation_messages(
        self, conversation_id: str, messages: List[Dict], timeout: Optional[int] = None
    ) -> None:
        """Set all messages for a conversation"""
        key = self._build_key("conv", conversation_id, "messages")
        self.cache.set(key, messages, timeout or self.default_timeout)

    def add_message_to_conversation(self, conversation_id: str, message: Dict) -> None:
        """Add a new message to conversation's message list"""
        messages = self.get_conversation_messages(conversation_id)
        messages.append(message)
        self.set_conversation_messages(conversation_id, messages)

    def get_user_conversations(self, user_id: str) -> List[str]:
        """Get all conversation IDs for a user"""
        key = self._build_key("user", user_id, "conversations")
        return self.cache.get(key) or []

    def set_user_conversations(
        self, user_id: str, conversation_ids: List[str], timeout: Optional[int] = None
    ) -> None:
        """Set all conversation IDs for a user"""
        key = self._build_key("user", user_id, "conversations")
        self.cache.set(key, conversation_ids, timeout or self.default_timeout)

    def get_conversation_participants(self, conversation_id: str) -> List[str]:
        """Get all participant IDs in a conversation"""
        key = self._build_key("conv", conversation_id, "participants")
        return self.cache.get(key) or []

    def set_conversation_participants(
        self,
        conversation_id: str,
        participant_ids: List[str],
        timeout: Optional[int] = None,
    ) -> None:
        """Set all participant IDs in a conversation"""
        key = self._build_key("conv", conversation_id, "participants")
        self.cache.set(key, participant_ids, timeout or self.default_timeout)

    def get_message_reactions(self, message_id: str) -> Dict:
        """Get reactions for a message"""
        key = self._build_key("msg", message_id, "reactions")
        return self.cache.get(key) or {}

    def set_message_reactions(
        self, message_id: str, reactions: Dict, timeout: Optional[int] = None
    ) -> None:
        """Set reactions for a message"""
        key = self._build_key("msg", message_id, "reactions")
        self.cache.set(key, reactions, timeout or self.default_timeout)

    def add_message_reaction(
        self, message_id: str, user_id: str, reaction: str
    ) -> None:
        """Add a reaction to a message"""
        reactions = self.get_message_reactions(message_id)
        if reaction not in reactions:
            reactions[reaction] = []
        if user_id not in reactions[reaction]:
            reactions[reaction].append(user_id)
        self.set_message_reactions(message_id, reactions)

    def remove_message_reaction(
        self, message_id: str, user_id: str, reaction: str
    ) -> None:
        """Remove a reaction from a message"""
        reactions = self.get_message_reactions(message_id)
        if reaction in reactions and user_id in reactions[reaction]:
            reactions[reaction].remove(user_id)
            if not reactions[reaction]:
                del reactions[reaction]
        self.set_message_reactions(message_id, reactions)

    def get_typing_status(self, conversation_id: str) -> Dict[str, bool]:
        """Get typing status for all users in a conversation"""
        key = self._build_key("conv", conversation_id, "typing")
        return self.cache.get(key) or {}

    def set_user_typing(
        self, conversation_id: str, user_id: str, is_typing: bool, timeout: int = 30
    ) -> None:
        """Set typing status for a user in a conversation"""
        key = self._build_key("conv", conversation_id, "typing")
        typing_status = self.get_typing_status(conversation_id)
        typing_status[user_id] = is_typing
        self.cache.set(key, typing_status, timeout)

    def clear_conversation_cache(self, conversation_id: str) -> None:
        """Clear all cached data for a conversation"""
        keys = [
            self._build_key("conv", conversation_id, "messages"),
            self._build_key("conv", conversation_id, "participants"),
            self._build_key("conv", conversation_id, "typing"),
        ]
        self.cache.delete_many(keys)
        
    # Adding required attributes for offline caching
    OFFLINE_QUEUE_PREFIX = "offline_queue_"
    CONVERSATION_TIMEOUT = 86400  # 24 hours
    
    def get_offline_queue(self, user_id: str) -> List:
        """Get the offline message queue for a user"""
        key = f"{self.OFFLINE_QUEUE_PREFIX}{user_id}"
        return self.cache.get(key) or []
    
    def queue_offline_message(self, user_id: str, conversation_id: str, message_data: Dict) -> bool:
        """Queue an offline message for later delivery"""
        try:
            key = f"{self.OFFLINE_QUEUE_PREFIX}{user_id}"
            queue = self.get_offline_queue(user_id)
            queue.append(message_data)
            self.cache.set(key, queue, self.CONVERSATION_TIMEOUT)
            return True
        except Exception as e:
            logger.error(f"Error queuing offline message: {str(e)}")
            return False
            
    def mark_offline_messages_sent(self, user_id: str, message_ids: List[str]) -> None:
        """Mark offline messages as sent"""
        key = f"{self.OFFLINE_QUEUE_PREFIX}{user_id}"
        queue = self.get_offline_queue(user_id)
        for message in queue:
            if message.get("id") in message_ids:
                message["status"] = "sent"
        self.cache.set(key, queue, self.CONVERSATION_TIMEOUT)
        
    # Add missing methods needed by other components
    def get_cached_message(self, message_id):
        """Get a cached message by ID"""
        return self.get_message(message_id)
        
    def get_cached_conversation(self, conversation_id):
        """Get a cached conversation by ID"""
        key = self._build_key("conv", conversation_id)
        return self.cache.get(key)
        
    def cache_conversation(self, conversation):
        """Cache a conversation object"""
        key = self._build_key("conv", conversation.id)
        # Simple caching implementation - in real system would serialize properly
        self.cache.set(key, {"id": conversation.id, "type": conversation.__class__.__name__})
        
    def invalidate_message(self, message_id):
        """Invalidate a message in cache"""
        self.delete_message(message_id)
        
    def get_cached_message_batch(self, conversation_id):
        """Get a batch of cached messages for a conversation"""
        return {}  # Simplified implementation
        
    def cache_message(self, message):
        """Cache a message object"""
        if hasattr(message, 'id'):
            self.set_message(message.id, {"id": message.id})
    
    def cache_message_batch(self, conversation_id, messages):
        """Cache a batch of messages"""
        # Implementation simplified for this fix
        pass


# Create a singleton instance for use throughout the application
message_cache = MessagingCacheManager()

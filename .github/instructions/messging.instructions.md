---
applyTo: '**'
---
1)# messaging/caches/cache_manager.py
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

    def queue_offline_message(
        self, user_id: str, conversation_id: str, message_data: Dict
    ) -> bool:
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
        self.cache.set(
            key, {"id": conversation.id, "type": conversation.__class__.__name__}
        )

    def invalidate_message(self, message_id):
        """Invalidate a message in cache"""
        self.delete_message(message_id)

    def get_cached_message_batch(self, conversation_id):
        """Get a batch of cached messages for a conversation"""
        return {}  # Simplified implementation

    def cache_message(self, message):
        """Cache a message object"""
        if hasattr(message, "id"):
            self.set_message(message.id, {"id": message.id})

    def cache_message_batch(self, conversation_id, messages):
        """Cache a batch of messages"""
        # Implementation simplified for this fix
        pass


# Create a singleton instance for use throughout the application
message_cache = MessagingCacheManager()

2)from django.core.cache import cache
from django.conf import settings

# Cache timeout settings (in seconds)
REACTION_CACHE_TIMEOUT = getattr(settings, "REACTION_CACHE_TIMEOUT", 3600)  # 1 hour
EDIT_HISTORY_CACHE_TIMEOUT = getattr(
    settings, "EDIT_HISTORY_CACHE_TIMEOUT", 3600 * 24
)  # 24 hours
PARTICIPANTS_CACHE_TIMEOUT = getattr(
    settings, "PARTICIPANTS_CACHE_TIMEOUT", 3600
)  # 1 hour
READ_RECEIPTS_CACHE_TIMEOUT = getattr(
    settings, "READ_RECEIPTS_CACHE_TIMEOUT", 1800
)  # 30 minutes


def generate_message_key(base_key: str, message_id: str) -> str:
    """Generate a cache key for message-related data"""
    return f"message:{base_key}:{message_id}"


def generate_conversation_key(base_key: str, conversation_id: str) -> str:
    """Generate a cache key for conversation-related data"""
    return f"conversation:{base_key}:{conversation_id}"


def generate_user_key(base_key: str, user_id: str) -> str:
    """Generate a cache key for user-related data"""
    return f"user:{base_key}:{user_id}"


class MessageCache:
    @staticmethod
    def get_reactions(message_id: str) -> dict:
        key = generate_message_key("reactions", message_id)
        return cache.get(key)

    @staticmethod
    def set_reactions(message_id: str, reactions: dict) -> None:
        key = generate_message_key("reactions", message_id)
        cache.set(key, reactions, timeout=REACTION_CACHE_TIMEOUT)

    @staticmethod
    def delete_reactions(message_id: str) -> None:
        key = generate_message_key("reactions", message_id)
        cache.delete(key)


class EditHistoryCache:
    @staticmethod
    def get_history(message_id: str) -> list:
        key = generate_message_key("edit_history", message_id)
        return cache.get(key)

    @staticmethod
    def set_history(message_id: str, history: list) -> None:
        key = generate_message_key("edit_history", message_id)
        cache.set(key, history, timeout=EDIT_HISTORY_CACHE_TIMEOUT)

    @staticmethod
    def delete_history(message_id: str) -> None:
        key = generate_message_key("edit_history", message_id)
        cache.delete(key)


class ConversationCache:
    @staticmethod
    def get_participants(conversation_id: str) -> list:
        key = generate_conversation_key("participants", conversation_id)
        return cache.get(key)

    @staticmethod
    def set_participants(conversation_id: str, participants: list) -> None:
        key = generate_conversation_key("participants", conversation_id)
        cache.set(key, participants, timeout=PARTICIPANTS_CACHE_TIMEOUT)

    @staticmethod
    def delete_participants(conversation_id: str) -> None:
        key = generate_conversation_key("participants", conversation_id)
        cache.delete(key)


class ReadReceiptCache:
    @staticmethod
    def get_receipts(message_id: str) -> list:
        key = generate_message_key("read_receipts", message_id)
        return cache.get(key)

    @staticmethod
    def set_receipts(message_id: str, receipts: list) -> None:
        key = generate_message_key("read_receipts", message_id)
        cache.set(key, receipts, timeout=READ_RECEIPTS_CACHE_TIMEOUT)

    @staticmethod
    def add_receipt(message_id: str, user_id: str) -> None:
        key = generate_message_key("read_receipts", message_id)
        receipts = cache.get(key, [])
        if user_id not in receipts:
            receipts.append(user_id)
            cache.set(key, receipts, timeout=READ_RECEIPTS_CACHE_TIMEOUT)

3)# messaging/caches/offline_handler.py
import logging
import time
from typing import Dict, Any
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .cache_manager import message_cache
from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation

User = get_user_model()
logger = logging.getLogger(__name__)


class OfflineMessageHandler:
    """
    Handles synchronization of messages created while offline.

    This class manages:
    - Processing queued offline messages when connection is restored
    - Creating database records from cached message data
    - Handling conflict resolution for messages created while offline
    """

    def __init__(self):
        # Map conversation types to their message models
        self.message_models = {
            "OneToOneConversation": OneToOneMessage,
            "GroupConversation": GroupMessage,
        }

        # Map conversation types to their conversation models
        self.conversation_models = {
            "OneToOneConversation": OneToOneConversation,
            "GroupConversation": GroupConversation,
        }

    def sync_offline_messages(self, user_id: int) -> Dict[str, Any]:
        """
        Process all offline messages for a user and persist them to the database.

        Args:
            user_id: The user ID whose offline messages should be synced

        Returns:
            Dict with results of the sync operation, including success count, error count, and errors
        """
        try:
            # Get all queued messages
            offline_queue = message_cache.get_offline_queue(user_id)
            if not offline_queue:
                return {
                    "success_count": 0,
                    "error_count": 0,
                    "already_synced": 0,
                    "errors": [],
                }

            logger.info(
                f"Processing {len(offline_queue)} offline messages for user {user_id}"
            )

            result = {
                "success_count": 0,
                "error_count": 0,
                "already_synced": 0,
                "errors": [],
            }

            successful_ids = []

            # Process each message
            for message_data in offline_queue:
                if message_data.get("status") == "sent":
                    result["already_synced"] += 1
                    continue

                try:
                    # Process the message and get the result
                    success, new_message_id, error_msg = self._process_offline_message(
                        message_data, user_id
                    )

                    if success:
                        result["success_count"] += 1
                        successful_ids.append(message_data.get("id"))

                        # Update message data with new database ID
                        message_data["db_id"] = new_message_id
                        message_data["status"] = "sent"
                        message_data["sent_at"] = time.time()
                    else:
                        result["error_count"] += 1
                        result["errors"].append(
                            {"message_id": message_data.get("id"), "error": error_msg}
                        )
                except Exception as e:
                    logger.error(
                        f"Error processing offline message: {str(e)}", exc_info=True
                    )
                    result["error_count"] += 1
                    result["errors"].append(
                        {"message_id": message_data.get("id"), "error": str(e)}
                    )

            # Mark successful messages as sent
            if successful_ids:
                message_cache.mark_offline_messages_sent(user_id, successful_ids)

            return result

        except Exception as e:
            logger.error(
                f"Failed to sync offline messages for user {user_id}: {str(e)}",
                exc_info=True,
            )
            return {
                "success_count": 0,
                "error_count": 1,
                "errors": [{"error": f"Sync failed: {str(e)}"}],
            }

    @transaction.atomic
    def _process_offline_message(
        self, message_data: Dict[str, Any], user_id: int
    ) -> tuple:
        """
        Process a single offline message and persist it to the database.

        Args:
            message_data: The cached message data
            user_id: The user ID who created the message

        Returns:
            Tuple of (success, new_message_id, error_message)
        """
        try:
            # Get required data
            conversation_id = message_data.get("conversation_id")
            content = message_data.get("content")
            message_type = message_data.get("message_type", "text")

            if not conversation_id or not content:
                return False, None, "Missing required message data"

            # Get the conversation
            conversation_data = message_cache.get_cached_conversation(conversation_id)
            if not conversation_data:
                return False, None, f"Conversation {conversation_id} not found in cache"

            # Determine conversation type and get appropriate model
            conversation_type = conversation_data.get("type")
            if not conversation_type or conversation_type not in self.message_models:
                return False, None, f"Invalid conversation type: {conversation_type}"

            # Get conversation from database
            conversation_model = self.conversation_models[conversation_type]
            try:
                conversation = conversation_model.objects.get(id=conversation_id)
            except conversation_model.DoesNotExist:
                return (
                    False,
                    None,
                    f"Conversation {conversation_id} not found in database",
                )

            # Check if user is a participant
            if not self._is_user_participant(conversation, user_id):
                return False, None, "User is not a participant in this conversation"

            # Get user instance
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return False, None, f"User {user_id} not found"

            # Create the message
            message_model = self.message_models[conversation_type]
            message = message_model(
                conversation=conversation,
                sender=user,
                content=content,
                message_type=message_type,
                metadata=message_data.get("metadata", {}),
                timestamp=timezone.now(),
            )

            message.save()

            # Update conversation last activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])

            # Cache the new message
            message_cache.cache_message(message)

            return True, message.id, None

        except Exception as e:
            logger.error(f"Error processing offline message: {str(e)}", exc_info=True)
            return False, None, str(e)

    def _is_user_participant(self, conversation, user_id: int) -> bool:
        """
        Check if user is a participant in the conversation.

        Args:
            conversation: The conversation object
            user_id: The user ID to check

        Returns:
            bool: True if user is a participant, False otherwise
        """
        if hasattr(conversation, "participants"):
            return conversation.participants.filter(id=user_id).exists()
        elif hasattr(conversation, "user") and hasattr(conversation.user, "id"):
            return conversation.user.id == user_id
        return False

    def clear_synced_messages(self, user_id: int) -> bool:
        """
        Clear synced messages from the offline queue.

        Args:
            user_id: The user ID whose synced messages should be cleared

        Returns:
            bool: Success status
        """
        try:
            # Get all queued messages
            offline_queue = message_cache.get_offline_queue(user_id)
            if not offline_queue:
                return True

            # Filter to keep only non-synced messages
            new_queue = [msg for msg in offline_queue if msg.get("status") != "sent"]

            # If the queue changed, update it
            if len(new_queue) != len(offline_queue):
                queue_key = f"{message_cache.OFFLINE_QUEUE_PREFIX}{user_id}"
                message_cache.cache.set(
                    queue_key, new_queue, message_cache.CONVERSATION_TIMEOUT
                )

            return True
        except Exception as e:
            logger.error(f"Error clearing synced messages for user {user_id}: {str(e)}")
            return False


# Create a singleton instance for use throughout the application
offline_handler = OfflineMessageHandler()

4)# messaging/caches/serializers.py
import logging
import json
import time
from datetime import datetime
from django.utils import timezone
from typing import Dict, Any, Optional, Union
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class CacheJSONEncoder(DjangoJSONEncoder):
    """Custom JSON encoder that handles additional types for message caching."""

    def default(self, obj):
        # Handle datetime objects
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle sets by converting to lists
        if isinstance(obj, set):
            return list(obj)
        # Handle bytes by decoding to utf-8
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return super().default(obj)


class MessageSerializer:
    """
    Handles serialization and deserialization of messages for caching.

    This class provides methods to:
    - Convert model objects to cacheable dictionaries
    - Convert cached dictionaries back to structured data
    - Handle different message formats for different conversation types
    """

    @classmethod
    def serialize_for_cache(cls, obj: Any, obj_type: str = None) -> Optional[Dict]:
        """
        Serialize an object for caching based on its type.

        Args:
            obj: The object to serialize
            obj_type: Optional type hint ('message', 'conversation', etc.)

        Returns:
            Dict or None if serialization fails
        """
        try:
            if not obj:
                return None

            # Determine object type if not provided
            if obj_type is None:
                if hasattr(obj, "content") and hasattr(obj, "sender"):
                    obj_type = "message"
                elif hasattr(obj, "participants"):
                    obj_type = "conversation"
                else:
                    obj_type = "unknown"

            # Call appropriate serializer based on type
            if obj_type == "message":
                return cls._serialize_message(obj)
            elif obj_type == "conversation":
                return cls._serialize_conversation(obj)
            else:
                logger.warning(f"Unknown object type for serialization: {obj_type}")
                return None

        except Exception as e:
            logger.error(f"Serialization error: {str(e)}", exc_info=True)
            return None

    @classmethod
    def _serialize_message(cls, message) -> Dict:
        """
        Serialize a message object to a cacheable dictionary.

        Args:
            message: Message model instance

        Returns:
            Dict representation of the message
        """
        try:
            # Basic message data that all message types should have
            data = {
                "id": message.id,
                "content": message.content,
                "conversation_id": message.conversation_id,
                "timestamp": cls._format_datetime(message.timestamp),
            }

            # Add sender information if available
            if hasattr(message, "sender") and message.sender:
                data["sender_id"] = message.sender.id
                data["sender_name"] = message.sender.username
                if hasattr(message.sender, "get_full_name"):
                    data["sender_full_name"] = message.sender.get_full_name()
                if hasattr(message.sender, "user_type"):
                    data["sender_type"] = message.sender.user_type

            # Add edit history if present
            if hasattr(message, "edited") and message.edited:
                data["edited"] = True
                data["edited_at"] = cls._format_datetime(message.edited_at)
                if hasattr(message, "edit_history") and message.edit_history:
                    data["edit_history"] = message.edit_history

            # Add reactions if present
            if hasattr(message, "reactions") and message.reactions:
                data["reactions"] = message.reactions

            # Add message type if present
            if hasattr(message, "message_type"):
                data["message_type"] = message.message_type

            # Add metadata if present
            if hasattr(message, "metadata") and message.metadata:
                data["metadata"] = message.metadata

            # Add read status if present
            if hasattr(message, "read_by"):
                try:
                    data["read_by"] = list(message.read_by.values_list("id", flat=True))
                except Exception:
                    # Fallback if read_by is not a QuerySet (e.g., if it's already a list)
                    data["read_by"] = list(message.read_by)

            return data

        except Exception as e:
            logger.error(
                f"Error serializing message {getattr(message, 'id', 'unknown')}: {str(e)}",
                exc_info=True,
            )
            # Return minimal valid data
            return {
                "id": getattr(message, "id", 0),
                "content": getattr(message, "content", ""),
                "conversation_id": getattr(message, "conversation_id", 0),
                "timestamp": cls._format_datetime(
                    getattr(message, "timestamp", timezone.now())
                ),
                "error": str(e),
            }

    @classmethod
    def _serialize_conversation(cls, conversation) -> Dict:
        """
        Serialize a conversation object to a cacheable dictionary.

        Args:
            conversation: Conversation model instance

        Returns:
            Dict representation of the conversation
        """
        try:
            # Basic conversation data
            data = {
                "id": conversation.id,
                "created_at": cls._format_datetime(conversation.created_at),
                "last_activity": cls._format_datetime(conversation.last_activity),
                "is_active": conversation.is_active,
                "type": conversation.__class__.__name__,
            }

            # Add participants if available
            if (
                hasattr(conversation, "participants")
                and conversation.participants.exists()
            ):
                participants_data = []
                for user in conversation.participants.all():
                    user_data = {
                        "id": user.id,
                        "username": user.username,
                    }

                    # Add user type if available
                    if hasattr(user, "user_type"):
                        user_data["user_type"] = user.user_type

                    # Add full name if available
                    if hasattr(user, "get_full_name"):
                        user_data["full_name"] = user.get_full_name()

                    participants_data.append(user_data)

                data["participants"] = participants_data
                data["participant_ids"] = list(
                    conversation.participants.values_list("id", flat=True)
                )

            # Add group-specific fields
            if hasattr(conversation, "name"):
                data["name"] = conversation.name

            if hasattr(conversation, "description"):
                data["description"] = conversation.description

            if hasattr(conversation, "is_private"):
                data["is_private"] = conversation.is_private

            return data

        except Exception as e:
            logger.error(
                f"Error serializing conversation {getattr(conversation, 'id', 'unknown')}: {str(e)}",
                exc_info=True,
            )
            # Return minimal valid data
            return {
                "id": getattr(conversation, "id", 0),
                "type": conversation.__class__.__name__,
                "created_at": cls._format_datetime(
                    getattr(conversation, "created_at", timezone.now())
                ),
                "error": str(e),
            }

    @staticmethod
    def _format_datetime(dt) -> Union[str, float]:
        """
        Format a datetime object for caching.

        Args:
            dt: Datetime object

        Returns:
            float: Unix timestamp
        """
        if not dt:
            return time.time()

        if isinstance(dt, datetime):
            return dt.timestamp()

        # If it's already a timestamp or string, return as is
        return dt

    @classmethod
    def to_json(cls, data: Any) -> str:
        """
        Convert data to JSON string with custom encoder.

        Args:
            data: The data to convert

        Returns:
            str: JSON representation
        """
        try:
            return json.dumps(data, cls=CacheJSONEncoder)
        except Exception as e:
            logger.error(f"JSON serialization error: {str(e)}", exc_info=True)
            return json.dumps({"error": str(e)})

    @classmethod
    def from_json(cls, json_str: str) -> Any:
        """
        Convert JSON string back to Python object.

        Args:
            json_str: JSON string

        Returns:
            Deserialized object
        """
        try:
            if not json_str:
                return None
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"JSON deserialization error: {str(e)}", exc_info=True)
            return None

5)# messaging/caches/service_cache.py
import logging
import time
from typing import Dict, List, Any
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from .cache_manager import message_cache
from .offline_handler import offline_handler

logger = logging.getLogger(__name__)


class MessageServiceCache:
    """
    Service layer cache for messaging.

    This class provides high-level caching operations for message services:
    - Cached message retrieval with database fallback
    - Batch message loading and caching
    - Conversation management with caching
    - Offline message handling integration
    """

    def __init__(self):
        self.message_cache = message_cache
        self.offline_handler = offline_handler

    def get_message(self, message_id: int, message_model):
        """
        Get a message by ID with caching.

        Args:
            message_id: The message ID
            message_model: The message model class

        Returns:
            Message object or None
        """
        try:
            # Try to get from cache first
            cached_message = self.message_cache.get_cached_message(message_id)

            if cached_message:
                logger.debug(f"Cache hit for message {message_id}")
                return cached_message

            # Not in cache, get from database
            logger.debug(f"Cache miss for message {message_id}, fetching from DB")
            message = message_model.objects.get(id=message_id)

            # Cache the message for next time
            self.message_cache.cache_message(message)

            return message

        except ObjectDoesNotExist:
            logger.warning(f"Message {message_id} not found in database")
            return None
        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {str(e)}")
            # Fall back to database directly on cache error
            try:
                return message_model.objects.get(id=message_id)
            except Exception:
                return None

    def get_messages_for_conversation(
        self,
        conversation_id: int,
        message_model,
        limit: int = 50,
        before_id: int = None,
        after_id: int = None,
    ) -> List[Any]:
        """
        Get messages for a conversation with caching.

        Args:
            conversation_id: The conversation ID
            message_model: The message model class
            limit: Maximum number of messages to return
            before_id: Get messages before this ID
            after_id: Get messages after this ID

        Returns:
            List of message objects
        """
        try:
            # Check if we have a cached batch that might satisfy this request
            cached_batch = self.message_cache.get_cached_message_batch(conversation_id)

            # Try to use cached batch if it exists and we're not doing pagination
            if cached_batch and not before_id and not after_id:
                logger.debug(f"Using cached batch for conversation {conversation_id}")
                # Get message IDs sorted by timestamp (newest first)
                sorted_ids = sorted(
                    cached_batch.keys(),
                    key=lambda k: cached_batch[k].get("timestamp", 0),
                    reverse=True,
                )

                # Limit to requested count
                sorted_ids = sorted_ids[:limit]

                # Get messages from batch
                return [cached_batch[msg_id] for msg_id in sorted_ids]

            # Need to fetch from database
            logger.debug(
                f"Fetching messages for conversation {conversation_id} from DB"
            )

            # Build query
            query = Q(conversation_id=conversation_id)
            if before_id:
                query &= Q(id__lt=before_id)
            if after_id:
                query &= Q(id__gt=after_id)

            # Fetch messages
            messages = list(
                message_model.objects.filter(query)
                .order_by("-timestamp")
                .select_related("sender")
                .prefetch_related("read_by")[:limit]
            )

            # Cache this batch
            self.message_cache.cache_message_batch(conversation_id, messages)

            return messages

        except Exception as e:
            logger.error(
                f"Error getting messages for conversation {conversation_id}: {str(e)}"
            )
            # Fall back to database directly
            try:
                query = Q(conversation_id=conversation_id)
                if before_id:
                    query &= Q(id__lt=before_id)
                if after_id:
                    query &= Q(id__gt=after_id)

                return list(
                    message_model.objects.filter(query).order_by("-timestamp")[:limit]
                )
            except Exception:
                return []

    def get_conversation(self, conversation_id: int, conversation_model):
        """
        Get a conversation by ID with caching.

        Args:
            conversation_id: The conversation ID
            conversation_model: The conversation model class

        Returns:
            Conversation object or None
        """
        try:
            # Try to get from cache first
            cached_conversation = self.message_cache.get_cached_conversation(
                conversation_id
            )

            if cached_conversation:
                logger.debug(f"Cache hit for conversation {conversation_id}")
                return cached_conversation

            # Not in cache, get from database
            logger.debug(
                f"Cache miss for conversation {conversation_id}, fetching from DB"
            )
            conversation = conversation_model.objects.get(id=conversation_id)

            # Cache the conversation for next time
            self.message_cache.cache_conversation(conversation)

            return conversation

        except ObjectDoesNotExist:
            logger.warning(f"Conversation {conversation_id} not found in database")
            return None
        except Exception as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
            # Fall back to database directly on cache error
            try:
                return conversation_model.objects.get(id=conversation_id)
            except Exception:
                return None

    def get_user_conversations(self, user_id: int, conversation_model):
        """
        Get all conversations for a user with caching.

        Args:
            user_id: The user ID
            conversation_model: The conversation model class

        Returns:
            List of conversation objects
        """
        try:
            # Check if we have cached conversation IDs for this user
            conversation_ids = self.message_cache.get_user_conversations(user_id)

            if conversation_ids:
                logger.debug(f"Using cached conversation IDs for user {user_id}")
                conversations = []
                # Get each conversation from cache or database
                for conv_id in conversation_ids:
                    conv = self.get_conversation(conv_id, conversation_model)
                    if conv:
                        conversations.append(conv)
                return conversations

            # No cached IDs, fetch from database
            logger.debug(f"Fetching conversations for user {user_id} from DB")
            conversations = list(
                conversation_model.objects.filter(participants=user_id)
                .select_related()
                .prefetch_related("participants")
                .order_by("-last_activity")
            )

            # Cache each conversation
            for conv in conversations:
                self.message_cache.cache_conversation(conv)

            return conversations

        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
            # Fall back to database directly
            try:
                return list(
                    conversation_model.objects.filter(participants=user_id).order_by(
                        "-last_activity"
                    )
                )
            except Exception:
                return []

    def process_offline_messages(self, user_id: int) -> Dict:
        """
        Process and persist any offline messages for a user.

        Args:
            user_id: The user ID

        Returns:
            Dict with results of sync operation
        """
        return self.offline_handler.sync_offline_messages(user_id)

    def queue_offline_message(
        self,
        user_id: int,
        conversation_id: int,
        content: str,
        message_type: str = "text",
    ) -> Dict:
        """
        Queue a message to be sent when the user comes back online.

        Args:
            user_id: The sender's user ID
            conversation_id: The conversation ID
            content: Message content
            message_type: Type of message

        Returns:
            Dict with status and message ID
        """
        try:
            # Generate a temporary ID for the message
            temp_id = f"offline_{int(time.time())}_{user_id}_{conversation_id}"

            # Create message data
            message_data = {
                "id": temp_id,
                "content": content,
                "sender_id": user_id,
                "conversation_id": conversation_id,
                "timestamp": time.time(),
                "message_type": message_type,
                "metadata": {"offline": True, "queued_at": time.time()},
            }

            # Queue the message
            success = self.message_cache.queue_offline_message(
                user_id, conversation_id, message_data
            )

            if success:
                return {
                    "status": "queued",
                    "message_id": temp_id,
                    "queued_at": message_data["metadata"]["queued_at"],
                }
            else:
                return {"status": "error", "error": "Failed to queue message"}

        except Exception as e:
            logger.error(f"Error queueing offline message: {str(e)}")
            return {"status": "error", "error": str(e)}

    @transaction.atomic
    def save_message(self, message_obj) -> bool:
        """
        Save a message to database and cache.

        Args:
            message_obj: Message object to save

        Returns:
            bool: Success status
        """
        try:
            # Save to database
            message_obj.save()

            # Cache the message
            self.message_cache.cache_message(message_obj)

            # Update conversation cache
            conversation = message_obj.conversation
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])
            self.message_cache.cache_conversation(conversation)

            return True
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return False

    def update_message(self, message_obj, update_fields: List[str] = None) -> bool:
        """
        Update a message in database and cache.

        Args:
            message_obj: Message object to update
            update_fields: Fields to update

        Returns:
            bool: Success status
        """
        try:
            # Save to database
            if update_fields:
                message_obj.save(update_fields=update_fields)
            else:
                message_obj.save()

            # Update cache
            self.message_cache.cache_message(message_obj)

            return True
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}")
            return False

    def invalidate_message(self, message_id: int) -> bool:
        """
        Invalidate a message in cache.

        Args:
            message_id: The message ID to invalidate

        Returns:
            bool: Success status
        """
        try:
            self.message_cache.invalidate_message(message_id)
            return True
        except Exception as e:
            logger.error(f"Error invalidating message cache: {str(e)}")
            return False


# Create a singleton instance for use throughout the application
message_service_cache = MessageServiceCache()

6)# messaging/caches/signal_handlers.py
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation
from .cache_manager import message_cache

logger = logging.getLogger(__name__)

# ===== Message Signals =====


@receiver(post_save, sender=OneToOneMessage)
@receiver(post_save, sender=GroupMessage)
def cache_message_on_save(sender, instance, created, **kwargs):
    """Cache a message when it's created or updated."""
    try:
        # Cache the message
        message_cache.cache_message(instance)

        # Update conversation last activity
        conversation = instance.conversation
        conversation.last_activity = timezone.now()
        conversation.save(update_fields=["last_activity"])

        # Cache the conversation
        message_cache.cache_conversation(conversation)

        logger.debug(
            f"Message {instance.id} cached {'(created)' if created else '(updated)'}"
        )
    except Exception as e:
        logger.error(f"Error caching message {instance.id}: {str(e)}", exc_info=True)


@receiver(pre_save, sender=OneToOneMessage)
@receiver(pre_save, sender=GroupMessage)
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
            if (
                hasattr(old_instance, "reactions")
                and hasattr(instance, "reactions")
                and old_instance.reactions != instance.reactions
            ):
                instance._reactions_changed = True

        except sender.DoesNotExist:
            pass
    except Exception as e:
        logger.error(f"Error in pre-save message edit cache: {str(e)}", exc_info=True)


@receiver(post_delete, sender=OneToOneMessage)
@receiver(post_delete, sender=GroupMessage)
def invalidate_message_cache(sender, instance, **kwargs):
    """Remove a message from cache when it's deleted."""
    try:
        # Invalidate message in cache
        message_cache.invalidate_message(instance.id)

        # Update conversation last activity
        conversation = instance.conversation
        conversation.last_activity = timezone.now()
        conversation.save(update_fields=["last_activity"])

        # Cache the updated conversation
        message_cache.cache_conversation(conversation)

        logger.debug(f"Message {instance.id} removed from cache")
    except Exception as e:
        logger.error(
            f"Error invalidating message cache for {instance.id}: {str(e)}",
            exc_info=True,
        )


# ===== Conversation Signals =====


@receiver(post_save, sender=OneToOneConversation)
@receiver(post_save, sender=GroupConversation)
def cache_conversation_on_save(sender, instance, created, **kwargs):
    """Cache a conversation when it's created or updated."""
    try:
        # Cache the conversation
        message_cache.cache_conversation(instance)

        if created:
            # For new conversations, update user conversation lists
            for participant in instance.participants.all():
                message_cache._add_to_user_conversations(participant.id, instance.id)

        logger.debug(
            f"Conversation {instance.id} cached {'(created)' if created else '(updated)'}"
        )
    except Exception as e:
        logger.error(
            f"Error caching conversation {instance.id}: {str(e)}", exc_info=True
        )


@receiver(post_delete, sender=OneToOneConversation)
@receiver(post_delete, sender=GroupConversation)
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
            user_convs_key = (
                f"{message_cache.USER_CONVERSATIONS_PREFIX}{participant.id}"
            )
            conversation_ids = message_cache.cache.get(user_convs_key, [])
            if instance.id in conversation_ids:
                conversation_ids.remove(instance.id)
                message_cache.cache.set(
                    user_convs_key,
                    conversation_ids,
                    message_cache.CONVERSATION_LIST_TIMEOUT,
                )

        logger.debug(f"Conversation {instance.id} removed from cache")
    except Exception as e:
        logger.error(
            f"Error cleaning up cache for conversation {instance.id}: {str(e)}",
            exc_info=True,
        )

7)# messaging/mixins/edit_history.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import logging
from messaging.serializers import EditHistorySerializer

logger = logging.getLogger(__name__)


class EditHistoryMixin:
    """Mixin to add edit history functionality to message viewsets"""

    @extend_schema(
        description="Get edit history for a message",
        summary="Get Edit History",
        tags=["Message"],
        responses={
            200: EditHistorySerializer(many=True),
            400: {"description": "Bad Request"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["get"], url_path="edit_history")
    def edit_history(self, request, pk=None):
        """Retrieve the edit history of a specific message."""
        try:
            message = self.get_object()
            if not hasattr(message, "edit_history"):
                return Response(
                    {"error": "This message does not have an edit history."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Assuming `edit_history` is a field or method on the message model
            history = message.edit_history
            serializer = EditHistorySerializer(history, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

8)# messaging/mixins/reactions.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import logging

logger = logging.getLogger(__name__)


class ReactionMixin:
    """Mixin to add reaction functionality to message viewsets"""

    @extend_schema(
        description="Add a reaction to a message",
        summary="Add Reaction",
        tags=["Message"],
        request={"type": "object", "properties": {"reaction": {"type": "string"}}},
        responses={
            200: {"description": "Reaction added successfully"},
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["post"], url_path="add-reaction")
    def add_reaction(self, request, pk=None):
        """Add a reaction to a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Get the reaction from request data
            reaction_type = request.data.get("reaction")
            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Add the reaction
            if not hasattr(message, "add_reaction"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Store the user who added this reaction for notification purposes
            message._last_reactor = request.user
            message._last_reaction_type = reaction_type

            # Add the reaction
            message.add_reaction(request.user, reaction_type)

            # Return the updated message
            serializer = self.get_serializer(message)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error adding reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Remove a reaction from a message",
        summary="Remove Reaction",
        tags=["Message"],
        request={"type": "object", "properties": {"reaction": {"type": "string"}}},
        responses={
            200: {"description": "Reaction removed successfully"},
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["delete"], url_path="remove-reaction")
    def remove_reaction(self, request, pk=None):
        """Remove a reaction from a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Get the reaction from request data
            reaction_type = request.data.get("reaction")
            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if message supports reactions
            if not hasattr(message, "remove_reaction"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Remove the reaction
            if (
                reaction_type in message.reactions
                and request.user.id in message.reactions[reaction_type]
            ):
                message.remove_reaction(request.user)

                # Return the updated message
                serializer = self.get_serializer(message)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Reaction not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            logger.error(f"Error removing reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Get all reactions for a message",
        summary="Get Reactions",
        tags=["Message"],
        responses={
            200: {"description": "Reactions retrieved successfully"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["get"], url_path="reactions")
    def get_reactions(self, request, pk=None):
        """Get all reactions for a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Check if message has reactions
            if not hasattr(message, "reactions"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get the reactions
            reactions = message.reactions

            # Enhance reaction data with user information
            enhanced_reactions = {}
            from django.contrib.auth import get_user_model

            User = get_user_model()

            for reaction_type, user_ids in reactions.items():
                users = User.objects.filter(id__in=user_ids).values("id", "username")
                enhanced_reactions[reaction_type] = list(users)

            return Response(enhanced_reactions, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting reactions: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

9)# messaging/models/base.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class BaseConversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="%(class)s_conversations",
        blank=True,  # Allow blank to prevent immediate validation issues
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)
    archive_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        # When the conversation exists (has a pk), ensure it has at least 2 participants.
        if self.pk and self.participants.count() < 2:
            raise ValidationError("Conversation must have at least 2 participants")

    def archive(self):
        """Archive the conversation"""
        self.archived = True
        self.archive_date = timezone.now()
        self.save()

    def unarchive(self):
        """Unarchive the conversation"""
        self.archived = False
        self.archive_date = None
        self.save()

    def __str__(self):
        return f"Conversation {self.pk}"


class BaseMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)s_sent_messages",
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="%(class)s_read_messages", blank=True
    )
    reactions = models.JSONField(default=dict)

    # Edit tracking fields
    edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_edited_messages",
    )

    # Soft deletion fields
    deleted = models.BooleanField(default=False)
    deletion_time = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_deleted_messages",
    )

    # Message metadata
    message_type = models.CharField(
        max_length=20,
        choices=[
            ("text", "Text Message"),
            ("image", "Image Message"),
            ("file", "File Attachment"),
            ("system", "System Message"),
        ],
        default="text",
    )
    metadata = models.JSONField(
        default=dict, help_text="Store additional message metadata"
    )

    # Edit history field
    edit_history = models.JSONField(
        default=list, help_text="List of previous message versions"
    )

    class Meta:
        abstract = True
        ordering = ["timestamp"]  # Changed from ["-timestamp"] to ascending order
        indexes = [
            models.Index(fields=["timestamp"]),  # Changed from ["-timestamp"]
            models.Index(
                fields=["sender", "timestamp"]
            ),  # Changed from ["sender", "-timestamp"]
            models.Index(
                fields=["message_type", "timestamp"]
            ),  # Changed from ["message_type", "-timestamp"]
        ]

    def soft_delete(self, deleted_by_user):
        """Soft delete a message"""
        try:
            self.deleted = True
            self.deletion_time = timezone.now()
            self.deleted_by = deleted_by_user
            self.save()

            logger.info(f"Message {self.id} soft deleted by user {deleted_by_user.id}")
            return True
        except Exception as e:
            logger.error(f"Error soft deleting message {self.id}: {str(e)}")
            return False

    def edit_message(self, new_content: str, edited_by_user):
        """Edit message content with version tracking"""
        try:
            MessageEditHistory.objects.create(
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.id,
                previous_content=self.content,
                edited_by=edited_by_user,
            )
            self.content = new_content
            self.edited = True
            self.edited_at = timezone.now()
            self.edited_by = edited_by_user
            self.save()
            return True
        except Exception as e:
            logger.error(f"Error editing message {self.id}: {str(e)}")
            return False

    def add_reaction(self, user, reaction_type):
        """Add a reaction to the message"""
        if not self.reactions:
            self.reactions = {}

        user_id = str(user.id)
        if user_id not in self.reactions:
            self.reactions[user_id] = reaction_type
            self.save(update_fields=["reactions"])

    def remove_reaction(self, user):
        """Remove a user's reaction from the message"""
        if self.reactions:
            user_id = str(user.id)
            if user_id in self.reactions:
                del self.reactions[user_id]
                self.save(update_fields=["reactions"])

    @property
    def reactions_changed(self):
        """Check if reactions have changed since load"""
        return hasattr(self, "_reactions_changed") and self._reactions_changed

    @property
    def last_reactor(self):
        """Get the last user who reacted"""
        return getattr(self, "_last_reactor", None)

    @property
    def last_reaction_type(self):
        """Get the type of the last reaction"""
        return getattr(self, "_last_reaction_type", None)

    @last_reaction_type.setter
    def last_reaction_type(self, value):
        """Set the type of the last reaction"""
        self._last_reaction_type = value


class MessageEditHistory(models.Model):
    """Tracks edit history for any message type using a generic foreign key."""

    # Generic Foreign Key fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    message = GenericForeignKey("content_type", "object_id")

    # Edit history fields
    previous_content = models.TextField(help_text="The content before this edit")
    edited_at = models.DateTimeField(auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="message_edits",
    )

    class Meta:
        verbose_name = "Message Edit History"
        verbose_name_plural = "Message Edit Histories"
        ordering = ["-edited_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["edited_at"]),
        ]

    def __str__(self):
        return f"Edit by {self.edited_by} at {self.edited_at}"

    @property
    def edit_summary(self):
        """Returns a human-readable summary of the edit"""
        return {
            "editor": self.edited_by.get_full_name() or self.edited_by.username
            if self.edited_by
            else "Unknown",
            "timestamp": self.edited_at,
            "previous_content": (
                self.previous_content[:100] + "..."
                if len(self.previous_content) > 100
                else self.previous_content
            ),
        }

10)# messaging/models/group.py
from django.db import models
from django.conf import settings
from .base import BaseConversation, BaseMessage


class GroupConversation(BaseConversation):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="moderated_groups"
    )
    is_private = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class GroupMessage(BaseMessage):
    conversation = models.ForeignKey(
        GroupConversation, on_delete=models.CASCADE, related_name="messages"
    )
    message_type = models.CharField(
        max_length=10, choices=[("text", "Text"), ("system", "System")], default="text"
    )
    media = models.FileField(
        upload_to="uploads/group/",
        blank=True,
        null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    def clean(self):
        super().clean()
        if self.media:
            from media_handler.utils import validate_file_extension

            validate_file_extension(self.media.name, [".jpg", ".png", ".mp4", ".pdf"])

    def __str__(self):
        return f"Message by {self.sender} in {self.conversation}"

11)# messaging/models/one_to_one.py
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from .base import BaseConversation, BaseMessage
from django.contrib.postgres.fields import ArrayField


class OneToOneConversationParticipant(models.Model):
    conversation = models.ForeignKey("OneToOneConversation", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = (("conversation", "user"),)


class OneToOneConversation(BaseConversation):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="OneToOneConversationParticipant",
        related_name="onetoone_conversations",
    )

    class Meta:
        verbose_name = "One-to-One Conversation"
        verbose_name_plural = "One-to-One Conversations"

    def clean(self):
        super().clean()
        if self.pk and self.participants.count() != 2:
            raise ValidationError(
                "One-to-one conversations must have exactly 2 participants."
            )


@receiver(m2m_changed, sender=OneToOneConversation.participants.through)
def validate_one_to_one_participants(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        if instance.pk and instance.participants.count() != 2:
            raise ValidationError(
                "One-to-one conversations must have exactly 2 participants."
            )


class OneToOneMessage(BaseMessage):
    conversation = models.ForeignKey(
        OneToOneConversation, on_delete=models.CASCADE, related_name="messages"
    )
    edit_history = ArrayField(
        models.JSONField(),
        default=list,
        blank=True,
        help_text="History of message edits",
    )
    media = models.FileField(
        upload_to="uploads/one_to_one/",
        blank=True,
        null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    def clean(self):
        super().clean()
        if self.media:
            from media_handler.utils import validate_file_extension

            validate_file_extension(self.media.name, [".jpg", ".png", ".mp4", ".pdf"])

13)from rest_framework import serializers


class OneToOneConversationMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField(default="one_to_one")


class GroupConversationMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField(default="group")


class AllConversationsSerializer(serializers.Serializer):
    one_to_one = OneToOneConversationMinimalSerializer(many=True)
    groups = GroupConversationMinimalSerializer(many=True)

14)# messaging/serializers/group.py
from rest_framework import serializers
from django.conf import settings
from ..models.group import GroupConversation, GroupMessage
import logging

logger = logging.getLogger(__name__)


class GroupConversationSerializer(serializers.ModelSerializer):
    participant_count = serializers.IntegerField(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = GroupConversation
        fields = [
            "id",
            "name",
            "description",
            "participants",
            "moderators",
            "is_private",
            "created_at",
            "participant_count",
            "unread_count",
            "last_message",
            "archived",
            "archive_date",
        ]
        read_only_fields = ["moderators", "created_at", "archived", "archive_date"]

    def validate(self, attrs):
        """Validate group creation/update"""
        if self.instance is None:  # Create operation
            # Validate group name
            name = attrs.get("name", "").strip()
            if not name:
                raise serializers.ValidationError({"name": "Group name is required"})
            if len(name) > 100:
                raise serializers.ValidationError({"name": "Group name too long"})

            # Validate participants
            participants = attrs.get("participants", [])
            if len(participants) < 2:
                raise serializers.ValidationError(
                    {"participants": "Group must have at least 2 participants"}
                )
            if (
                len(participants)
                > settings.GROUP_SETTINGS["MAX_PARTICIPANTS_PER_GROUP"]
            ):
                raise serializers.ValidationError(
                    {
                        "participants": f"Maximum {settings.GROUP_SETTINGS['MAX_PARTICIPANTS_PER_GROUP']} participants allowed"
                    }
                )

        return attrs

    def get_last_message(self, obj):
        """Get latest message details"""
        try:
            message = obj.messages.order_by("-timestamp").first()
            if not message:
                return None

            return {
                "id": message.id,
                "content": message.content[:100]
                + ("..." if len(message.content) > 100 else ""),
                "sender_name": message.sender.get_full_name()
                or message.sender.username,
                "timestamp": message.timestamp,
            }
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None


class GroupMessageSerializer(serializers.ModelSerializer):
    MESSAGE_TYPE_CHOICES = (
        ("text", "Text Message"),
        ("system", "System Message"),
    )

    content = serializers.CharField(
        max_length=5000, help_text="Enter the message content"
    )

    conversation = serializers.PrimaryKeyRelatedField(
        queryset=GroupConversation.objects.all(), help_text="Select the conversation"
    )

    message_type = serializers.ChoiceField(choices=MESSAGE_TYPE_CHOICES, default="text")

    edit_history = serializers.ListField(child=serializers.CharField(), default=list)

    media = serializers.FileField(
        required=False,
        allow_null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    class Meta:
        model = GroupMessage
        fields = [
            "id",
            "conversation",
            "content",
            "message_type",
            "sender",
            "timestamp",
            "edit_history",
            "media",
        ]
        read_only_fields = ["id", "sender", "timestamp"]


class AddParticipantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(
        help_text="ID of the user to add as a participant."
    )


class EditHistorySerializer(serializers.Serializer):
    editor = serializers.CharField(help_text="The user who edited the message.")
    timestamp = serializers.DateTimeField(help_text="The time the edit was made.")
    previous_content = serializers.CharField(
        help_text="The content of the message before the edit."
    )


class GroupMessageSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = ["id", "content", "sender", "timestamp", "conversation"]


class GroupConversationSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupConversation
        fields = ["id", "name", "description", "participant_count"]

15)# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage
import logging

logger = logging.getLogger(__name__)


class OneToOneConversationSerializer(serializers.ModelSerializer):
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    other_user_name = serializers.SerializerMethodField()
    participant_id = serializers.IntegerField(
        write_only=True,
        required=False,
        help_text="ID of the participant for the conversation",
    )

    def __init__(self, *args, **kwargs):
        """Dynamically adjust fields based on the request method."""
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == "POST":
            self.fields["participant_id"].required = True
        else:
            self.fields.pop("participant_id", None)

    class Meta:
        model = OneToOneConversation
        fields = [
            "id",
            "participants",
            "created_at",
            "unread_count",
            "last_message",
            "other_participant",
            "other_user_name",
            "participant_id",
        ]
        read_only_fields = ["created_at", "unread_count"]

    def validate_participants(self, value):
        try:
            request = self.context.get("request")
            if not request:
                raise serializers.ValidationError("Request context is missing.")

            current_user = request.user
            if len(value) != 1:
                raise serializers.ValidationError(
                    "Must include exactly one other participant."
                )

            other_user = value[0]
            if current_user == other_user:
                raise serializers.ValidationError(
                    "Cannot create conversation with yourself."
                )

            # Check user types
            user_types = {current_user.user_type, other_user.user_type}
            if user_types != {"patient", "therapist"}:
                raise serializers.ValidationError(
                    "Conversation must have one patient and one therapist."
                )

            # Check existing conversation
            if self._conversation_exists(current_user, other_user):
                raise serializers.ValidationError(
                    "Conversation already exists between these users."
                )

            return value

        except Exception as e:
            logger.error(f"Error validating participants: {str(e)}")
            raise serializers.ValidationError("Invalid participants")

    def _conversation_exists(self, user1, user2):
        """Check if conversation exists between two users"""
        return (
            OneToOneConversation.objects.filter(participants=user1)
            .filter(participants=user2)
            .exists()
        )

    def get_last_message(self, obj):
        """Get the last message in the conversation with full media URL if exists."""
        try:
            message = obj.messages.last()
            if message:
                media_url = None
                if message.media:
                    request = self.context.get("request")
                    media_url = (
                        request.build_absolute_uri(message.media.url)
                        if request
                        else message.media.url
                    )
                return {
                    "id": message.id,
                    "content": message.content,
                    "timestamp": message.timestamp,
                    "sender_id": message.sender_id,
                    "sender_name": message.sender.username,
                    "media": media_url,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None

    def get_other_participant(self, obj):
        """Get details of the other participant."""
        try:
            request = self.context.get("request")
            if not request:
                return None

            other_user = obj.participants.exclude(id=request.user.id).first()
            if not other_user:
                return None

            return {
                "id": other_user.id,
                "username": other_user.username,
                "user_type": other_user.user_type,
            }
        except Exception as e:
            logger.error(f"Error getting other participant: {str(e)}")
            return None

    def get_other_user_name(self, obj):
        """Get the full name or username of the other participant."""
        request = self.context.get("request")
        if not request:
            return None
        other_user = obj.participants.exclude(id=request.user.id).first()
        if other_user:
            return other_user.get_full_name() or other_user.username
        return None

    def create(self, validated_data):
        """Handle creation of a one-to-one conversation."""
        participant_id = validated_data.pop("participant_id", None)
        if not participant_id:
            raise serializers.ValidationError(
                {"participant_id": "This field is required."}
            )

        # Fetch the participant user
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            participant = User.objects.get(id=participant_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"participant_id": "User does not exist."}
            )

        # Create the conversation
        conversation = OneToOneConversation.objects.create()
        conversation.participants.add(self.context["request"].user, participant)
        return conversation


class OneToOneMessageSerializer(serializers.ModelSerializer):
    MESSAGE_TYPE_CHOICES = (
        ("text", "Text Message"),
        ("system", "System Message"),
    )

    content = serializers.CharField(
        max_length=5000, help_text="Enter the message content"
    )

    conversation = serializers.PrimaryKeyRelatedField(
        queryset=OneToOneConversation.objects.all(),
        help_text="Select the conversation",
        required=False,  # Make conversation optional for updates
    )

    message_type = serializers.ChoiceField(choices=MESSAGE_TYPE_CHOICES, default="text")

    sender_name = serializers.CharField(source="sender.username", read_only=True)

    media = serializers.FileField(
        required=False,
        allow_null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    def __init__(self, *args, **kwargs):
        """Dynamically adjust fields based on the request method."""
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            if request.method == "POST":
                # Ensure `conversation` is included for POST requests
                self.fields["conversation"].required = True
            elif request.method in ["GET", "PATCH", "PUT"]:
                # Exclude `conversation` for other methods
                self.fields.pop("conversation", None)

    class Meta:
        model = OneToOneMessage
        fields = [
            "id",
            "conversation",
            "content",
            "message_type",
            "sender",
            "sender_name",
            "timestamp",
            "media",
        ]
        read_only_fields = ["id", "sender", "sender_name", "timestamp"]

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authenticated user is required to send a message."
            )

        validated_data["sender"] = (
            request.user
        )  # Set the sender to the authenticated user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update the message content and other fields."""
        instance.content = validated_data.get("content", instance.content)
        instance.message_type = validated_data.get(
            "message_type", instance.message_type
        )
        instance.media = validated_data.get("media", instance.media)
        instance.save()
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep.get("media"):
            request = self.context.get("request")
            rep["media"] = (
                request.build_absolute_uri(instance.media.url)
                if request
                else instance.media.url
            )
        return rep

16)# messaging/services/connection_manager.py
import logging
from datetime import timedelta
from channels.layers import get_channel_layer
from django.utils import timezone
from django.conf import settings
import asyncio

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Service for managing WebSocket connections state, including:
    - Tracking active connections
    - Detecting stale connections
    - Performing cleanup operations
    """

    def __init__(self):
        self.active_connections = {}  # Map of user_id -> {connection_info}
        self.channel_layer = get_channel_layer()
        self.stale_threshold = getattr(
            settings, "WEBSOCKET_STALE_THRESHOLD", 120
        )  # seconds
        self.cleanup_interval = getattr(
            settings, "WEBSOCKET_CLEANUP_INTERVAL", 300
        )  # seconds

    def register_connection(self, user_id, channel_name, connection_type="messaging"):
        """Register a new WebSocket connection"""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}

        self.active_connections[user_id][channel_name] = {
            "type": connection_type,
            "connected_at": timezone.now(),
            "last_activity": timezone.now(),
        }

        logger.info(
            f"Registered WebSocket connection for user {user_id}: {channel_name}"
        )

    def update_connection_activity(self, user_id, channel_name):
        """Update the last activity timestamp for a connection"""
        if (
            user_id in self.active_connections
            and channel_name in self.active_connections[user_id]
        ):
            self.active_connections[user_id][channel_name]["last_activity"] = (
                timezone.now()
            )

    def unregister_connection(self, user_id, channel_name):
        """Unregister a WebSocket connection when it's closed"""
        if user_id in self.active_connections:
            if channel_name in self.active_connections[user_id]:
                del self.active_connections[user_id][channel_name]
                logger.info(
                    f"Unregistered WebSocket connection for user {user_id}: {channel_name}"
                )

            # If no more connections for this user, remove the user entry
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    def get_active_connections_count(self):
        """Get number of active connections"""
        connection_count = 0
        for user_id, connections in self.active_connections.items():
            connection_count += len(connections)
        return connection_count

    def get_user_connection_count(self, user_id):
        """Get number of active connections for a specific user"""
        if user_id in self.active_connections:
            return len(self.active_connections[user_id])
        return 0

    def is_user_online(self, user_id):
        """Check if a user has any active connections"""
        return (
            user_id in self.active_connections
            and len(self.active_connections[user_id]) > 0
        )

    async def cleanup_stale_connections(self):
        """Check and close stale connections"""
        now = timezone.now()
        stale_threshold = now - timedelta(seconds=self.stale_threshold)

        stale_connections = []

        # Identify stale connections
        for user_id, connections in self.active_connections.items():
            for channel_name, conn_info in connections.items():
                if conn_info["last_activity"] < stale_threshold:
                    stale_connections.append((user_id, channel_name))

        # Close stale connections
        for user_id, channel_name in stale_connections:
            logger.warning(
                f"Closing stale connection for user {user_id}: {channel_name}"
            )
            try:
                # Send close message to the connection
                await self.channel_layer.send(
                    channel_name,
                    {
                        "type": "websocket.close",
                        "code": 4000,  # Custom code for stale connection
                    },
                )

                # Remove from our tracking
                self.unregister_connection(user_id, channel_name)
            except Exception as e:
                logger.error(f"Error closing stale connection: {str(e)}")

    async def start_cleanup_task(self):
        """Start periodic cleanup task"""
        while True:
            try:
                await self.cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in connection cleanup: {str(e)}")

            await asyncio.sleep(self.cleanup_interval)


# Create a singleton instance
connection_manager = WebSocketConnectionManager()

17)# messaging/services/connection_startup.py
import logging

logger = logging.getLogger(__name__)


class ConnectionManagerStartupHandler:
    """
    Handles the initialization of the WebSocket connection manager at application startup.
    Starts background tasks for monitoring and cleaning up connections.
    """

    @staticmethod
    def initialize():
        """Initialize connection manager and start background tasks"""
        try:
            from .connection_manager import connection_manager

            # This will run in the ASGI application startup
            logger.info("Initializing WebSocket connection manager")

            # In a production environment, this would be handled by the ASGI application
            # For development, we'll use this as a placeholder to document the process
            logger.info("WebSocket connection manager initialized")

            return connection_manager
        except Exception as e:
            logger.error(f"Failed to initialize connection manager: {str(e)}")
            return None

18)# messaging/services/constants.py
THERAPEUTIC_GUIDELINES = """You are Samantha, a mental health support assistant...
...existing guidelines..."""

ERROR_MESSAGES = {
    "Invalid input": "I couldn't understand that message. Could you please rephrase it?",
    "Service unavailable": "I need a moment to gather my thoughts. Could we try again shortly?",
    "Internal error": "I'm experiencing some confusion right now. Let's take a brief pause.",
}

"""Constants for the messaging service."""

# Cache keys and timeouts
MESSAGE_CACHE_KEY = "message_{message_id}"
CONVERSATION_CACHE_KEY = "conversation_{conversation_id}"
CONVERSATION_MESSAGES_CACHE_KEY = "conversation_messages_{conversation_id}"
CONVERSATION_PARTICIPANTS_CACHE_KEY = "conversation_participants_{conversation_id}"
USER_CONVERSATIONS_CACHE_KEY = "user_conversations_{user_id}"
MESSAGE_REACTIONS_CACHE_KEY = "message_reactions_{message_id}"
MESSAGE_EDIT_HISTORY_CACHE_KEY = "message_edit_history_{message_id}"

# Cache timeouts (in seconds)
CACHE_TIMEOUT = {
    "message": 3600,  # 1 hour
    "conversation": 3600,  # 1 hour
    "conversation_messages": 1800,  # 30 minutes
    "conversation_participants": 3600,  # 1 hour
    "user_conversations": 1800,  # 30 minutes
    "message_reactions": 1800,  # 30 minutes
    "message_edit_history": 3600,  # 1 hour
}

19)# messaging/services/message_delivery.py
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
        self.cache_timeout = getattr(
            settings, "MESSAGE_CACHE_TIMEOUT", 3600
        )  # 1 hour default
        self.cache_prefix = "msg_delivery_"
        # Add new cache settings
        self.bulk_cache_size = getattr(settings, "MESSAGE_BULK_CACHE_SIZE", 100)
        self.conversation_cache_timeout = getattr(
            settings, "CONVERSATION_CACHE_TIMEOUT", 7200
        )  # 2 hours

    def _get_cache_key(self, conversation_id: str, message_id: str = None) -> str:
        """Generate a cache key for message delivery"""
        if message_id:
            return f"{self.cache_prefix}conv_{conversation_id}_msg_{message_id}"
        return f"{self.cache_prefix}conv_{conversation_id}"

    def _cache_message(self, conversation_id: str, message_data: dict) -> None:
        """Cache message data for a conversation with improved bulk handling"""
        try:
            message_id = str(message_data.get("id", ""))
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
                pipeline.set(
                    conv_cache_key,
                    cached_messages,
                    timeout=self.conversation_cache_timeout,
                )

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

20)from typing import Dict, List
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from ..caches.cache_manager import MessagingCacheManager
from ..models.base import BaseMessage
from ..models.one_to_one import OneToOneMessage
from ..models.group import GroupMessage
from ..exceptions import MessageDeliveryError

logger = logging.getLogger(__name__)


class MessageService:
    """Service class for handling message operations with caching"""

    def __init__(self):
        self.cache_manager = MessagingCacheManager()
        self.channel_layer = get_channel_layer()

    def get_message(self, message_id: str, message_type: str = None) -> Dict:
        """Get a message with caching"""
        # Try cache first
        cached_message = self.cache_manager.get_message(message_id)
        if cached_message:
            return cached_message

        # If not in cache, get from database
        try:
            if message_type == "one_to_one":
                message = OneToOneMessage.objects.get(id=message_id)
            elif message_type == "group":
                message = GroupMessage.objects.get(id=message_id)
            else:
                message = BaseMessage.objects.get(id=message_id)

            # Convert to dict and cache
            message_data = message.to_dict()
            self.cache_manager.set_message(message_id, message_data)
            return message_data

        except ObjectDoesNotExist:
            return None

    def get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """Get all messages for a conversation with caching"""
        # Try cache first
        cached_messages = self.cache_manager.get_conversation_messages(conversation_id)
        if cached_messages:
            return cached_messages

        # If not in cache, get from database
        messages = BaseMessage.objects.filter(conversation_id=conversation_id).order_by(
            "created_at"
        )
        message_list = [msg.to_dict() for msg in messages]

        # Cache the messages
        self.cache_manager.set_conversation_messages(conversation_id, message_list)
        return message_list

    def create_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
        message_type: str = "one_to_one",
        **kwargs,
    ) -> Dict:
        """Create a new message with caching"""
        # Create message in database
        message_data = {
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "content": content,
            "created_at": timezone.now(),
            **kwargs,
        }

        if message_type == "one_to_one":
            message = OneToOneMessage.objects.create(**message_data)
        else:
            message = GroupMessage.objects.create(**message_data)

        # Convert to dict
        message_dict = message.to_dict()

        # Update cache
        self.cache_manager.set_message(str(message.id), message_dict)
        self.cache_manager.add_message_to_conversation(conversation_id, message_dict)

        # Send WebSocket update
        self._send_message_update(conversation_id, "message_created", message_dict)

        return message_dict

    def update_message(self, message_id: str, content: str, **kwargs) -> Dict:
        """Update a message with caching"""
        try:
            message = BaseMessage.objects.get(id=message_id)
            message.content = content
            message.updated_at = timezone.now()
            for key, value in kwargs.items():
                setattr(message, key, value)
            message.save()

            # Update cache
            message_dict = message.to_dict()
            self.cache_manager.set_message(message_id, message_dict)

            # Send WebSocket update
            self._send_message_update(
                str(message.conversation_id), "message_updated", message_dict
            )

            return message_dict

        except ObjectDoesNotExist:
            return None

    def delete_message(self, message_id: str) -> bool:
        """Delete a message with cache cleanup"""
        try:
            message = BaseMessage.objects.get(id=message_id)
            conversation_id = str(message.conversation_id)

            # Delete from database
            message.delete()

            # Clean up cache
            self.cache_manager.delete_message(message_id)

            # Remove from conversation messages cache
            cached_messages = self.cache_manager.get_conversation_messages(
                conversation_id
            )
            if cached_messages:
                cached_messages = [
                    msg for msg in cached_messages if str(msg.get("id")) != message_id
                ]
                self.cache_manager.set_conversation_messages(
                    conversation_id, cached_messages
                )

            # Send WebSocket update
            self._send_message_update(
                conversation_id, "message_deleted", {"id": message_id}
            )

            return True

        except ObjectDoesNotExist:
            return False

    def add_reaction(self, message_id: str, user_id: str, reaction: str) -> bool:
        """Add a reaction to a message"""
        self.cache_manager.add_message_reaction(message_id, user_id, reaction)
        # Update database
        try:
            message = BaseMessage.objects.get(id=message_id)
            message.add_reaction(user_id, reaction)
            return True
        except ObjectDoesNotExist:
            return False

    def remove_reaction(self, message_id: str, user_id: str, reaction: str) -> bool:
        """Remove a reaction from a message"""
        self.cache_manager.remove_message_reaction(message_id, user_id, reaction)
        # Update database
        try:
            message = BaseMessage.objects.get(id=message_id)
            if reaction in message.reactions and user_id in message.reactions[reaction]:
                message.reactions[reaction].remove(user_id)
                if not message.reactions[reaction]:
                    del message.reactions[reaction]
                message.save(update_fields=["reactions"])

                # Send WebSocket update
                conversation_id = str(message.conversation_id)
                message_dict = message.to_dict()
                self._send_message_update(
                    conversation_id, "reaction_removed", message_dict
                )

                return True
            return False
        except ObjectDoesNotExist:
            logger.error(f"Message {message_id} not found when removing reaction")
            return False

    def update_typing_status(
        self, conversation_id: str, user_id: str, is_typing: bool = True
    ) -> None:
        """Update typing status for a user"""
        self.cache_manager.set_user_typing(conversation_id, user_id, is_typing)
        # Send WebSocket update
        self._send_typing_update(conversation_id, user_id, is_typing)

    def _send_message_update(
        self, conversation_id: str, event_type: str, message_data: Dict
    ) -> None:
        """Send message update via WebSocket"""
        if not self.channel_layer:
            logger.warning("No channel layer available for WebSocket message delivery")
            return

        try:
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "chat.message",
                    "event_type": event_type,
                    "message": message_data,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send message update: {str(e)}")
            raise MessageDeliveryError(f"Error sending WebSocket message: {str(e)}")

    def _send_typing_update(
        self, conversation_id: str, user_id: str, is_typing: bool
    ) -> None:
        """Send typing status update via WebSocket"""
        if not self.channel_layer:
            return

        try:
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {"type": "typing.update", "user_id": user_id, "is_typing": is_typing},
            )
        except Exception as e:
            logger.error(f"Failed to send typing update: {str(e)}")
            raise MessageDeliveryError(
                f"Error sending WebSocket typing update: {str(e)}"
            )

21)from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation


class MessagingService:
    """Core messaging service for handling message operations"""

    def __init__(self):
        self.one_to_one_model = OneToOneMessage
        self.group_model = GroupMessage

    def send_message(self, sender, conversation_id, content, message_type="one_to_one"):
        """Send a message in a conversation"""
        if message_type == "one_to_one":
            conversation = OneToOneConversation.objects.get(id=conversation_id)
            return self.one_to_one_model.objects.create(
                sender=sender, conversation=conversation, content=content
            )
        elif message_type == "group":
            conversation = GroupConversation.objects.get(id=conversation_id)
            return self.group_model.objects.create(
                sender=sender, conversation=conversation, content=content
            )

    def get_conversation_messages(self, conversation_id, message_type="one_to_one"):
        """Get all messages in a conversation"""
        if message_type == "one_to_one":
            return self.one_to_one_model.objects.filter(
                conversation_id=conversation_id
            ).order_by("timestamp")
        elif message_type == "group":
            return self.group_model.objects.filter(
                conversation_id=conversation_id
            ).order_by("timestamp")

23)# messaging/signals/handlers.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

from ..models.base import BaseMessage
from ..models.one_to_one import OneToOneMessage
from ..models.group import GroupMessage
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
def update_conversation_on_message_change(sender, instance, created, **kwargs):
    from messaging.services.message_delivery import message_delivery_service

    # Update conversation timestamp
    conversation = instance.conversation
    conversation.last_activity = timezone.now()
    conversation.save()

    # Send WebSocket update only for new messages or edited messages
    if created or getattr(instance, "edited", False):
        try:
            event_type = "message_created" if created else "message_updated"

            # Prepare message data
            message_data = {
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
                "read_by": [],  # Initialize empty read receipts
            }

            # Use the unified service to send the message
            user_id = str(instance.sender.id) if instance.sender else None
            message_delivery_service.send_message_update(
                conversation_id=str(conversation.id),
                event_type=event_type,
                message_data=message_data,
                user_id=user_id,
            )

            logger.debug(f"Sent WebSocket {event_type} for message {instance.id}")

        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}", exc_info=True)

24)from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from messaging.models.one_to_one import OneToOneConversation
from messaging.models.group import GroupConversation
from messaging.serializers.one_to_one import OneToOneConversationSerializer
from messaging.serializers.group import GroupConversationSerializer


class AllConversationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        one_to_one = OneToOneConversation.objects.filter(participants=user)
        groups = GroupConversation.objects.filter(participants=user)
        one_to_one_data = OneToOneConversationSerializer(
            one_to_one, many=True, context={"request": request}
        ).data
        groups_data = GroupConversationSerializer(
            groups, many=True, context={"request": request}
        ).data
        return Response({"one_to_one": one_to_one_data, "groups": groups_data})

25)# messaging/views/group.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
)

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import GroupConversationSerializer, GroupMessageSerializer
from messaging.permissions import IsParticipantOrModerator
from messaging.throttling import GroupMessageThrottle
from ..mixins.edit_history import EditHistoryMixin
from ..mixins.reactions import ReactionMixin

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all group conversations where the authenticated user is a participant.",
        summary="List Group Conversations",
        tags=["Group Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve details of a specific group conversation.",
        summary="Retrieve Group Conversation",
        tags=["Group Conversation"],
    ),
    create=extend_schema(
        description="Create a new group conversation and automatically add the creator as a participant and moderator.",
        summary="Create Group Conversation",
        tags=["Group Conversation"],
    ),
    update=extend_schema(
        description="Update details of a group conversation.",
        summary="Update Group Conversation",
        tags=["Group Conversation"],
    ),
    partial_update=extend_schema(
        description="Partially update a group conversation.",
        summary="Patch Group Conversation",
        tags=["Group Conversation"],
    ),
    destroy=extend_schema(
        description="Delete a group conversation.",
        summary="Delete Group Conversation",
        tags=["Group Conversation"],
    ),
)
class GroupConversationViewSet(viewsets.ModelViewSet):
    queryset = GroupConversation.objects.all()
    serializer_class = GroupConversationSerializer
    permission_classes = [IsParticipantOrModerator]
    throttle_classes = [GroupMessageThrottle]

    def get_queryset(self):
        """Fetch all groups the user is involved in."""
        user = self.request.user
        logger.debug(f"Fetching groups for user: {user.id}")
        groups = GroupConversation.objects.filter(participants=user)
        logger.debug(f"Groups found: {groups.count()}")
        return groups

    def get_serializer_class(self):
        """Return the appropriate serializer class based on the action."""
        if self.action == "add_participant":
            from ..serializers.group import AddParticipantSerializer

            return AddParticipantSerializer
        return super().get_serializer_class()

    @transaction.atomic
    def perform_create(self, serializer):
        """Create group with atomic transaction (notifications removed)"""
        try:
            max_groups = getattr(settings, "MAX_GROUPS_PER_USER", 10)
            user_groups = GroupConversation.objects.filter(
                participants=self.request.user
            ).count()
            if user_groups >= max_groups:
                raise ValidationError(f"Maximum group limit ({max_groups}) reached")

            instance = serializer.save()
            instance.participants.add(self.request.user)
            instance.moderators.add(self.request.user)

            logger.info(
                f"Group conversation {instance.id} created by user {self.request.user.id}"
            )
            return instance

        except Exception as e:
            logger.error(f"Group creation failed: {str(e)}")
            raise ValidationError(f"Failed to create group: {str(e)}")

    @extend_schema(
        description="Create a new group conversation. Provide a name and any other allowed fields. The creator is automatically added as a participant and moderator.",
        summary="Create Group Conversation",
        request={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the group conversation",
                },
                # include any additional parameters as needed...
            },
            "required": ["name"],
        },
        responses={
            201: GroupConversationSerializer,
            400: OpenApiResponse(
                description="Bad Request – e.g., missing name or exceeding group limit."
            ),
        },
        examples=[
            OpenApiExample(
                "Valid Request",
                description="A valid request to create a group conversation",
                value={"name": "Test Group Conversation"},
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Add a user as a moderator to the group.",
        summary="Add Moderator",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to add as moderator.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(description="User added as moderator successfully."),
            400: OpenApiResponse(
                description="Bad Request – e.g., user not a participant."
            ),
            403: OpenApiResponse(description="Forbidden – insufficient permission."),
        },
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def add_moderator(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You don't have permission to add moderators."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        if not group.participants.filter(id=user.id).exists():
            return Response(
                {
                    "detail": "User must be a participant before being promoted to moderator."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        group.moderators.add(user)
        return Response(
            {"detail": f"User {user.username} is now a moderator."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        description="List all moderators of the group.",
        summary="List Moderators",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["get"])
    def moderators(self, request, pk=None):
        group = self.get_object()
        moderator_data = [
            {
                "id": mod.id,
                "username": mod.username,
                "first_name": mod.first_name,
                "last_name": mod.last_name,
                "email": mod.email,
            }
            for mod in group.moderators.all()
        ]
        return Response(moderator_data)

    @extend_schema(
        description="Add a participant to the group.",
        summary="Add Participant",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to add as participant.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(
                description="User added as participant successfully or already a member."
            ),
            400: OpenApiResponse(
                description="Bad Request – e.g., maximum participant limit reached."
            ),
            403: OpenApiResponse(
                description="Forbidden – only moderators can add participants."
            ),
        },
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"], url_path="add_participant")
    def add_participant(self, request, pk=None):
        """Add participant to group"""
        try:
            group = self.get_object()

            # Validate moderator permission
            if not group.moderators.filter(id=request.user.id).exists():
                return Response(
                    {"error": "Only moderators can add participants"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            user = get_object_or_404(get_user_model(), id=user_id)

            if (
                group.participants.count()
                >= settings.GROUP_SETTINGS["MAX_PARTICIPANTS_PER_GROUP"]
            ):
                return Response(
                    {"error": "Maximum participant limit reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if user is already a participant
            if group.participants.filter(id=user_id).exists():
                return Response(
                    {"message": f"{user.username} is already a member of this group"},
                    status=status.HTTP_200_OK,
                )

            group.participants.add(user)
            return Response(
                {"message": f"Added {user.username} to group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error adding participant: {str(e)}")
            return Response(
                {"error": "Failed to add participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Remove a participant from the group.",
        summary="Remove Participant",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to remove from the group.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(description="User removed from group successfully."),
            403: OpenApiResponse(description="Forbidden – insufficient permission."),
            500: OpenApiResponse(description="Internal server error."),
        },
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def remove_participant(self, request, pk=None):
        """Remove participant with proper validation (notifications removed)"""
        try:
            group = self.get_object()
            user_id = request.data.get("user_id")
            user = get_object_or_404(get_user_model(), id=user_id)

            if not (
                request.user.id == user_id
                or group.moderators.filter(id=request.user.id).exists()
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            group.participants.remove(user)
            group.moderators.remove(user)

            return Response(
                {"message": f"Removed {user.username} from group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error removing participant: {str(e)}")
            return Response(
                {"error": "Failed to remove participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Pin a message in the group conversation.",
        summary="Pin Message",
        request={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to be pinned.",
                }
            },
            "required": ["message_id"],
        },
        responses={
            200: OpenApiResponse(description="Message pinned successfully."),
            400: OpenApiResponse(description="Bad Request – message_id missing."),
            403: OpenApiResponse(
                description="Forbidden – only moderators can pin messages."
            ),
        },
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def pin_message(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Only moderators can pin messages"},
                status=status.HTTP_403_FORBIDDEN,
            )

        pinned_message_id = request.data.get("message_id")
        if not pinned_message_id:
            return Response(
                {"detail": "Message ID is required to pin a message."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group.pinned_message_id = pinned_message_id
        group.save()
        return Response(
            {"detail": "Message pinned successfully."}, status=status.HTTP_200_OK
        )

    @extend_schema(exclude=True)
    @action(detail=False, methods=["post"])
    def create_anonymous(self, request):
        """
        Create an anonymous group conversation. If a name is not provided, a default
        anonymous name is set and the conversation is marked as private.
        """
        data = request.data.copy()
        # Set default name if not provided
        if not data.get("name", "").strip():
            data["name"] = "Anonymous Conversation"
        # Force conversation to be private
        data["is_private"] = True
        # If participants list is not provided, set it as empty (perform_create will add request.user)
        if "participants" not in data:
            data["participants"] = []

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """Cache the group conversation list"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get group conversation with messages and participants"""
        try:
            # Get the conversation instance
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            response_data = serializer.data

            # Add participant information
            participants = instance.participants.all()
            response_data["participants_details"] = [
                {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "email": participant.email,
                }
                for participant in participants
            ]

            # Get messages for this conversation
            messages = instance.messages.all().order_by("timestamp")
            message_serializer = GroupMessageSerializer(messages, many=True)
            response_data["messages"] = message_serializer.data

            # Mark unread messages as read
            unread_messages = [
                message
                for message in messages
                if message.sender != request.user
                and request.user not in message.read_by.all()
            ]
            for message in unread_messages:
                message.read_by.add(request.user)

            # Only cache response data without messages to avoid stale message data
            cache_key = f"group_conversation_{instance.id}_basic"
            basic_data = dict(response_data)
            basic_data.pop("messages", None)
            cache.set(cache_key, basic_data, timeout=1800)

            return Response(response_data)

        except Exception as e:
            logger.error(
                f"Error retrieving group conversation: {str(e)}", exc_info=True
            )
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="search_messages")
    def search_messages(self, request):
        """Search group messages by content with partial matching."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        messages = GroupMessage.objects.filter(content__icontains=query)
        serializer = GroupMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="search_groups")
    def search_groups(self, request):
        """Search group conversations by name with partial matching."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        groups = GroupConversation.objects.filter(name__icontains=query)
        serializer = GroupConversationSerializer(groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="search_all")
    def search_all(self, request):
        """Unified search for group conversations and one-to-one conversations by name."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Search group conversations
        group_results = GroupConversation.objects.filter(name__icontains=query)
        group_serializer = GroupConversationSerializer(group_results, many=True)

        # Search one-to-one conversations
        from ..models.one_to_one import OneToOneConversation
        from ..serializers.one_to_one import OneToOneConversationSerializer

        one_to_one_results = OneToOneConversation.objects.filter(
            participants__username__icontains=query
        ).distinct()
        one_to_one_serializer = OneToOneConversationSerializer(
            one_to_one_results, many=True
        )

        return Response(
            {
                "groups": group_serializer.data,
                "one_to_one": one_to_one_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupMessageViewSet(ReactionMixin, EditHistoryMixin, viewsets.ModelViewSet):
    """
    API endpoints for Group Messages.

    Supports CRUD operations, edit history, and reactions.
    """

    serializer_class = GroupMessageSerializer
    permission_classes = [IsParticipantOrModerator]
    throttle_classes = [GroupMessageThrottle]

    def get_queryset(self):
        """Filter messages to include only those in groups the user participates in."""
        user = self.request.user
        return GroupMessage.objects.filter(conversation__participants=user).order_by(
            "timestamp"  # Changed from "-timestamp" to ascending order
        )

    def perform_create(self, serializer):
        """Set authenticated user as sender"""
        serializer.save(sender=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark a message as read by the current user."""
        try:
            message = self.get_object()
            message.read_by.add(request.user)

            # Send read receipt via WebSocket
            conversation_id = str(message.conversation.id)
            from messaging.services.message_delivery import message_delivery_service

            message_delivery_service.send_read_receipt(
                conversation_id=conversation_id,
                user_id=str(request.user.id),
                username=request.user.username,
                message_id=str(message.id),
            )

            return Response({"status": "marked as read"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}")
            return Response(
                {"error": f"Failed to mark message as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

26)# messaging/views/offline.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..caches.service_cache import message_service_cache
from ..throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

logger = logging.getLogger(__name__)


class OfflineMessageSyncView(APIView):
    """
    Synchronize offline messages when a user comes back online.

    This endpoint handles:
    - Processing queued offline messages
    - Syncing with the database
    - Reporting success/failure stats
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        summary="Synchronize offline messages",
        description="Process and persist messages that were created while offline",
        responses={
            200: OpenApiResponse(description="Messages successfully synced"),
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error during sync"),
        },
        tags=["messaging"],
    )
    def post(self, request):
        """Process messages that were created while the user was offline."""
        try:
            user_id = request.user.id

            # Process offline messages
            sync_result = message_service_cache.process_offline_messages(user_id)

            if sync_result["success_count"] > 0 or sync_result["already_synced"] > 0:
                return Response(
                    {
                        "status": "success",
                        "message": f"Successfully synced {sync_result['success_count']} messages",
                        "synced_count": sync_result["success_count"],
                        "already_synced": sync_result["already_synced"],
                        "errors": sync_result["errors"]
                        if sync_result["error_count"] > 0
                        else [],
                    },
                    status=status.HTTP_200_OK,
                )
            elif sync_result["error_count"] > 0:
                return Response(
                    {
                        "status": "partial_success",
                        "message": f"Encountered {sync_result['error_count']} errors during sync",
                        "synced_count": sync_result["success_count"],
                        "already_synced": sync_result["already_synced"],
                        "errors": sync_result["errors"],
                    },
                    status=status.HTTP_207_MULTI_STATUS,
                )
            else:
                return Response(
                    {
                        "status": "success",
                        "message": "No offline messages to sync",
                        "synced_count": 0,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error(f"Error during offline message sync: {str(e)}", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "message": "Failed to sync offline messages",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get offline message queue status",
        description="Get information about queued offline messages",
        responses={
            200: OpenApiResponse(description="Queue status retrieved successfully"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["messaging"],
    )
    def get(self, request):
        """Get information about queued offline messages."""
        try:
            user_id = request.user.id

            # Get offline queue
            offline_queue = message_service_cache.message_cache.get_offline_messages(
                user_id
            )

            # Count messages by status
            queued_count = 0
            sent_count = 0

            for msg in offline_queue:
                if msg.get("status") == "sent":
                    sent_count += 1
                else:
                    queued_count += 1

            return Response(
                {
                    "status": "success",
                    "queue_length": len(offline_queue),
                    "queued_count": queued_count,
                    "sent_count": sent_count,
                    "last_sync": request.user.last_login or request.user.date_joined,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error retrieving offline queue: {str(e)}", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "message": "Failed to retrieve offline queue",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Clear offline message queue",
        description="Clear the offline message queue for the current user",
        responses={
            200: OpenApiResponse(description="Queue cleared successfully"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["messaging"],
    )
    def delete(self, request):
        """Clear the offline message queue."""
        try:
            user_id = request.user.id

            # Clear offline queue
            success = message_service_cache.message_cache.clear_offline_messages(
                user_id
            )

            if success:
                return Response(
                    {"status": "success", "message": "Offline message queue cleared"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "status": "error",
                        "message": "Failed to clear offline message queue",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(f"Error clearing offline queue: {str(e)}", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "message": "Failed to clear offline queue",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

27)# messaging/views/one_to_one.py
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count, Max, Q, Prefetch
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiResponse,
)

from ..models.one_to_one import OneToOneConversation, OneToOneMessage
from ..serializers.one_to_one import (
    OneToOneConversationSerializer,
    OneToOneMessageSerializer,
)

# New corrected import
# Removed Firebase import
# from ..services.firebase import push_message  # DELETE THIS LINE
import logging
from ..mixins.edit_history import EditHistoryMixin
from ..mixins.reactions import ReactionMixin
from django.db import transaction

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all one-to-one conversations for the authenticated user.",
        summary="List One-to-One Conversations",
        tags=["One-to-One Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve detailed information for a specific one-to-one conversation.",
        summary="Retrieve One-to-One Conversation",
        tags=["One-to-One Conversation"],
    ),
    create=extend_schema(
        description="Create a new one-to-one conversation. Expects a request body with a 'participant_id'.",
        summary="Create One-to-One Conversation",
        request={
            "type": "object",
            "properties": {
                "participant_id": {
                    "type": "integer",
                    "description": "ID of the second participant (must be a patient if you're a therapist, or vice versa).",
                }
            },
            "required": ["participant_id"],
        },
        responses={
            201: OneToOneConversationSerializer,
            400: OpenApiResponse(
                description="Bad Request – e.g., missing or invalid participant_id."
            ),
            404: OpenApiResponse(description="Participant not found."),
        },
        examples=[
            OpenApiExample(
                "Valid Request",
                description="A valid request to create a one-to-one conversation.",
                value={"participant_id": 2},
            )
        ],
        tags=["One-to-One Conversation"],
    ),
)
class OneToOneConversationViewSet(viewsets.ModelViewSet):
    queryset = OneToOneConversation.objects.all()
    serializer_class = OneToOneConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get conversations that the current user is part of,
        with annotations for latest message info and unread count.
        """
        user = self.request.user

        # Prefetch recent messages for each conversation to avoid N+1 queries.
        message_prefetch = Prefetch(
            "messages",
            queryset=OneToOneMessage.objects.order_by("-timestamp"),
            to_attr="all_messages",
        )

        # Get all conversations with additional useful data.
        return (
            self.queryset.filter(participants=user)
            .prefetch_related("participants", message_prefetch)
            .annotate(
                last_message_time=Max("messages__timestamp"),
                unread_count=Count(
                    "messages",
                    filter=~Q(messages__read_by=user) & ~Q(messages__sender=user),
                ),
            )
            .order_by("-last_message_time")
        )

    @extend_schema(
        description="Enhanced list response that returns conversation data enriched with latest message preview and unread message counts. Supports pagination.",
        summary="Enhanced List One-to-One Conversations",
        tags=["One-to-One Conversation"],
    )
    def list(self, request, *args, **kwargs):
        """Enhanced list response with additional data."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                response_data = self.enrich_conversation_data(serializer.data)
                return self.get_paginated_response(response_data)
            serializer = self.get_serializer(queryset, many=True)
            response_data = self.enrich_conversation_data(serializer.data)
            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Enhanced detail view for a one-to-one conversation including participant info and recent message history. Also marks unread messages as read.",
        summary="Enhanced Retrieve One-to-One Conversation",
        tags=["One-to-One Conversation"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Enhanced detail view with messages."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            response_data = serializer.data

            # Add other participant information
            other_participants = instance.participants.exclude(id=request.user.id)
            response_data["other_participants"] = [
                {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "email": participant.email,
                }
                for participant in other_participants
            ]

            # Get recent messages (limit to last 20) and convert to list
            messages = list(instance.messages.all().order_by("-timestamp")[:20])
            message_serializer = OneToOneMessageSerializer(messages, many=True)
            response_data["messages"] = message_serializer.data

            # Mark messages as read using Python filtering on the list
            unread_messages = [
                message
                for message in messages
                if message.sender != request.user
                and request.user not in message.read_by.all()
            ]
            for message in unread_messages:
                message.read_by.add(request.user)

            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Retrieve messages for a specific conversation with support for cursor-based pagination using before and after parameters.",
        summary="List Conversation Messages",
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        """Get all messages for a conversation with proper pagination and consistent response format."""
        conversation = self.get_object()

        # Get messages in chronological order (oldest first)
        messages = OneToOneMessage.objects.filter(conversation=conversation).order_by(
            "timestamp"
        )

        # Apply pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = OneToOneMessageSerializer(
                page, many=True, context={"request": request}
            )
            response = self.get_paginated_response(serializer.data)
            return response

        # If pagination is not configured
        serializer = OneToOneMessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(
            {
                "results": serializer.data,
                "count": messages.count(),
            }
        )

    @extend_schema(
        description="Set the conversation status as 'typing' for the authenticated user.",
        summary="Set Typing Status",
        request=None,  # explicitly no body expected
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["post"])
    def typing(self, request, pk=None):
        conversation = self.get_object()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"conversation_{conversation.id}",
            {
                "type": "typing.indicator",
                "user_id": str(request.user.id),
                "username": request.user.username,
                "conversation_id": str(conversation.id),
                "is_typing": True,
            },
        )
        return Response({"status": "typing"}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Search for messages within the conversation that contain a specified query string.",
        summary="Search Conversation Messages",
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["get"])
    def search(self, request, pk=None):
        query = request.query_params.get("query")
        if not query:
            return Response(
                {"error": "Query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        messages = OneToOneMessage.objects.filter(
            content__icontains=query, conversation=pk
        )
        serializer = OneToOneMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def enrich_conversation_data(self, data):
        """Add additional information to conversation data for the UI."""
        user = self.request.user
        for conversation_data in data:
            conversation_id = conversation_data["id"]
            conversation = OneToOneConversation.objects.get(id=conversation_id)
            other_participants = conversation.participants.exclude(id=user.id)
            conversation_data["other_participants"] = [
                {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "email": participant.email,
                }
                for participant in other_participants
            ]
            # Slice the prefetched messages in Python
            latest_messages = getattr(conversation, "all_messages", [])[:5]
            if latest_messages:
                latest_message = latest_messages[0]
                conversation_data["latest_message"] = {
                    "id": latest_message.id,
                    "content": latest_message.content[:100]
                    + ("..." if len(latest_message.content) > 100 else ""),
                    "timestamp": latest_message.timestamp,
                    "is_from_current_user": latest_message.sender_id == user.id,
                    "sender_name": latest_message.sender.get_full_name()
                    or latest_message.sender.username,
                }
        return data

    def perform_create(self, serializer):
        user = self.request.user
        validated_participants = serializer.validated_data.get("participants", [])
        # Automatically include the authenticated user.
        validated_participants.append(user)
        serializer.save(participants=validated_participants)

    def create(self, request, *args, **kwargs):
        """
        Create a one-to-one conversation.
        Expects a payload with 'participant_id' for the second user.
        """
        other_participant_id = request.data.get("participant_id")
        if not other_participant_id:
            return Response(
                {"error": "Participant ID is required for one-to-one conversations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            User = get_user_model()
            other_participant = User.objects.get(id=other_participant_id)

            # First check if conversation already exists to avoid duplicates
            existing_conversation = (
                OneToOneConversation.objects.filter(participants=request.user)
                .filter(participants=other_participant)
                .first()
            )

            if existing_conversation:
                # Return existing conversation instead of creating a new one
                serializer = self.get_serializer(existing_conversation)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Validate user types if needed
            user_types = {request.user.user_type, other_participant.user_type}
            if user_types != {"patient", "therapist"}:
                return Response(
                    {"error": "Conversation must have one patient and one therapist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create new conversation with atomic transaction
            with transaction.atomic():
                conversation = OneToOneConversation.objects.create()
                conversation.participants.add(request.user, other_participant)

            serializer = self.get_serializer(conversation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response(
                {"error": "The specified participant does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to create conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OneToOneMessageViewSet(ReactionMixin, EditHistoryMixin, viewsets.ModelViewSet):
    queryset = OneToOneMessage.objects.all()
    serializer_class = OneToOneMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]

    def get_queryset(self):
        """Filter messages to include only those in conversations the user participates in."""
        user = self.request.user
        return OneToOneMessage.objects.filter(conversation__participants=user).order_by(
            "timestamp"  # Changed from "-timestamp" to ascending order
        )

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """Cache the message list for better performance"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get message with cache handling and debug logging."""
        message_id = kwargs.get("pk")
        logger.debug(f"Attempting to retrieve message with ID: {message_id}")

        # Check if the message exists in the queryset
        try:
            message = self.get_queryset().get(id=message_id)
            logger.debug(f"Message found: {message}")
        except OneToOneMessage.DoesNotExist:
            logger.error(
                f"Message with ID {message_id} does not exist or is not accessible."
            )
            return Response(
                {"detail": "No OneToOneMessage matches the given query."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Try to get from cache first
        cache_key = f"one_to_one_message_{message_id}"
        cached_message = cache.get(cache_key)
        if cached_message:
            logger.debug(f"Returning cached message for ID: {message_id}")
            return Response(cached_message)

        # Serialize and cache the response
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=3600)
        return response

    def perform_create(self, serializer):
        """Handle media uploads during message creation."""
        request = self.request
        if not request.user:
            raise serializers.ValidationError("Authenticated user is required.")

        # Pass the authenticated user as the sender
        serializer.save(sender=request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = (
            self.request
        )  # Ensure the request is passed to the serializer
        return context

    def get_serializer(self, *args, **kwargs):
        """Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

28)# messaging/apps.py
from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "messaging"

29)# messaging/consumers.py
import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from messaging.models.one_to_one import OneToOneMessage, OneToOneConversation
from messaging.models.group import GroupMessage, GroupConversation
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseWebSocketConsumer(AsyncWebsocketConsumer):
    """Base WebSocket consumer with common functionality"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_groups = set()
        self.conversation_type = None  # Will be set by subclasses

    async def get_user_conversation_groups(self):
        """Get all conversation groups the user participates in"""
        try:
            user_groups = []

            # Get one-to-one conversations
            one_to_one_convos = await self.get_user_one_to_one_conversations()
            for convo in one_to_one_convos:
                user_groups.append(f"conversation_{convo.id}")

            # Get group conversations
            group_convos = await self.get_user_group_conversations()
            for convo in group_convos:
                user_groups.append(f"conversation_{convo.id}")

            return user_groups
        except Exception as e:
            logger.error(f"Error getting user conversation groups: {str(e)}")
            return []

    @database_sync_to_async
    def get_user_one_to_one_conversations(self):
        """Get user's one-to-one conversations"""
        return list(OneToOneConversation.objects.filter(participants=self.user))

    @database_sync_to_async
    def get_user_group_conversations(self):
        """Get user's group conversations"""
        return list(GroupConversation.objects.filter(participants=self.user))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Cancel the heartbeat task if it exists
            if hasattr(self, "heartbeat_task") and self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task  # Await cancellation to ensure cleanup
                except asyncio.CancelledError:
                    pass

            # Leave conversation group
            if hasattr(self, "conversation_group_name"):
                await self.channel_layer.group_discard(
                    self.conversation_group_name, self.channel_name
                )

            # Leave user-specific group
            if hasattr(self, "user_group_name"):
                await self.channel_layer.group_discard(
                    self.user_group_name, self.channel_name
                )

            # Update user's offline status if this is their last connection
            if hasattr(self, "user") and not self.user.is_anonymous:
                await self.update_user_status(False)

                # Notify about user going offline
                if hasattr(self, "conversation_group_name"):
                    await self.channel_layer.group_send(
                        self.conversation_group_name,
                        {
                            "type": "user_offline",
                            "user_id": str(self.user.id),
                            "username": self.user.username,
                            "timestamp": timezone.now().isoformat(),
                        },
                    )

                logger.info(
                    f"User {self.user.id} disconnected from conversation {getattr(self, 'conversation_id', 'unknown')}"
                )

        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket data with improved heartbeat handling"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Update last ping time for any received message
            self.last_ping = timezone.now()

            # Handle heartbeat/ping messages
            if message_type in ["ping", "pong", "heartbeat"]:
                # Respond to client pings
                if message_type == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
                return
            elif message_type == "reconnect":
                await self.send(
                    text_data=json.dumps({"type": "reconnect_ack", "success": True})
                )
                return

            # Handle different message types
            if message_type == "message":
                await self.handle_new_message(data)
            elif message_type == "typing":
                await self.handle_typing_indicator(data)
            elif message_type == "read":
                await self.handle_read_receipt(data)
            elif message_type == "reaction":
                await self.handle_reaction(data)
            else:
                logger.warning(f"Unknown message type received: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}", exc_info=True)

    async def send_heartbeat(self):
        """Send periodic heartbeats with improved error handling"""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if connection is stale - more lenient timeout
                time_since_last_ping = (timezone.now() - self.last_ping).total_seconds()
                max_stale_time = self.heartbeat_interval * 5  # Increased tolerance

                if time_since_last_ping > max_stale_time:
                    logger.info(
                        f"Connection idle for user {self.user.id} ({time_since_last_ping}s), sending heartbeat"
                    )

                # Always send heartbeat, don't close for missing responses
                try:
                    await self.send(text_data=json.dumps({"type": "heartbeat"}))
                except Exception as send_error:
                    logger.error(f"Failed to send heartbeat: {str(send_error)}")
                    # Break the loop if we can't send, connection is likely dead
                    break

        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled normally")
        except Exception as e:
            logger.error(f"Error in heartbeat task: {str(e)}")

    async def handle_typing_indicator(self, data):
        """Handle typing indicator"""
        is_typing = data.get("is_typing", False)

        # Send to conversation group
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                "type": "typing.indicator",
                "user_id": str(self.user.id),
                "username": self.user.username,
                "is_typing": is_typing,
            },
        )

    async def handle_read_receipt(self, data):
        """Handle read receipt"""
        message_id = data.get("message_id")
        if not message_id:
            return

        # Mark as read in database
        success = await self.mark_message_read(message_id)
        if success:
            # Send to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "read.receipt",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "message_id": message_id,
                    "timestamp": timezone.now().isoformat(),
                },
            )

    async def handle_reaction(self, data):
        """Handle reaction event"""
        message_id = data.get("message_id")
        reaction = data.get("reaction")

        if not message_id or not reaction:
            return

        # Update reaction in database
        await self.update_message_reaction(data)

    async def update_message_reaction(self, data):
        """Update message reaction in database"""
        message_id = data.get("message_id")
        reaction = data.get("reaction")
        action = data.get("action", "add")  # add or remove

        if not message_id or not reaction:
            return

        try:
            # Handle reactions based on conversation type
            if self.conversation_type == "one_to_one":
                try:
                    message = await database_sync_to_async(OneToOneMessage.objects.get)(id=message_id)
                except ObjectDoesNotExist:
                    logger.error(f"One-to-one message with id {message_id} not found")
                    return
            else:  # group conversation
                try:
                    message = await database_sync_to_async(GroupMessage.objects.get)(id=message_id)
                except ObjectDoesNotExist:
                    logger.error(f"Group message with id {message_id} not found")
                    return

            # Update reaction logic
            if action == "add":
                await database_sync_to_async(message.add_reaction)(self.user, reaction)
            else:
                await database_sync_to_async(message.remove_reaction)(self.user, reaction)

            # Send to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "message.reaction",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "message_id": message_id,
                    "reaction": reaction,
                    "action": action,
                },
            )

        except Exception as e:
            logger.error(f"Error updating message reaction: {str(e)}", exc_info=True)

    # Event handlers for messages sent via channel layer

    async def chat_message(self, event):
        """Handle chat.message event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "event": event.get("event", "new_message"),
                    "message": event["message"],
                }
            )
        )

    async def typing_indicator(self, event):
        """Handle typing.indicator event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def read_receipt(self, event):
        """Handle read.receipt event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read_receipt",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "message_id": event["message_id"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def message_reaction(self, event):
        """
        Handle message.reaction event and send to WebSocket
        This gets called when someone adds/removes a reaction
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "reaction",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "message_id": event["message_id"],
                    "reaction": event["reaction"],
                    "action": event["action"],
                }
            )
        )

    async def participant_added(self, event):
        """Handle participant.added event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "participant_added",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "added_by": event["added_by"],
                }
            )
        )

    async def participant_removed(self, event):
        """Handle participant.removed event"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "participant_removed",
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "removed_by": event["removed_by"],
                }
            )
        )

    async def conversation_message(self, event):
        """Handle conversation.message event"""
        await self.send(text_data=json.dumps({"message": event["message"]}))

    async def user_online(self, event):
        """Handle user_online event"""
        if str(self.user.id) != event["user_id"]:  # Don't send to self
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence",
                        "event": "online",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    async def user_offline(self, event):
        """Handle user_offline event"""
        if str(self.user.id) != event["user_id"]:  # Don't send to self
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence",
                        "event": "offline",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark a message as read by the current user"""
        try:
            # Handle based on conversation type
            if self.conversation_type == "one_to_one":
                try:
                    message = OneToOneMessage.objects.get(id=message_id)
                    message.read_by.add(self.user)
                    return True
                except OneToOneMessage.DoesNotExist:
                    logger.warning(f"One-to-one message {message_id} not found for read receipt")
                    return False
            else:  # group conversation
                try:
                    message = GroupMessage.objects.get(id=message_id)
                    message.read_by.add(self.user)
                    return True
                except GroupMessage.DoesNotExist:
                    logger.warning(f"Group message {message_id} not found for read receipt")
                    return False

        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}", exc_info=True)
            return False

    @database_sync_to_async
    def update_user_status(self, online_status):
        """Update user's online status"""
        try:
            self.user.is_online = online_status
            self.user.last_seen = timezone.now()
            self.user.save(update_fields=["is_online", "last_seen"])
            return True
        except Exception as e:
            logger.error(f"Error updating user status: {str(e)}", exc_info=True)
            return False

    async def handle_new_message(self, data):
        """Abstract method to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_new_message")


class OneToOneChatConsumer(BaseWebSocketConsumer):
    """
    WebSocket consumer for handling one-to-one messaging.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_type = "one_to_one"

    async def connect(self):
        """Handle WebSocket connection for one-to-one chat"""
        try:
            # Get user and conversation ID
            self.user = self.scope["user"]
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.conversation_group_name = f"one_to_one_{self.conversation_id}"
            self.user_group_name = f"user_{self.user.id}"

            # Setup heartbeat monitoring
            self.last_ping = timezone.now()
            self.heartbeat_interval = getattr(
                settings, "WEBSOCKET_HEARTBEAT_INTERVAL", 30
            )
            self.heartbeat_task = None

            # Check if user is anonymous
            if self.user.is_anonymous:
                logger.warning(
                    f"Anonymous user tried to connect to {self.conversation_group_name}"
                )
                await self.close()
                return

            # Validate user's access to the one-to-one conversation
            has_access = await self.check_one_to_one_conversation_access()
            if not has_access:
                logger.warning(
                    f"User {self.user.id} tried to access unauthorized one-to-one conversation {self.conversation_id}"
                )
                await self.close()
                return

            # Add to conversation group
            await self.channel_layer.group_add(
                self.conversation_group_name, self.channel_name
            )

            # Add to user-specific group for private notifications
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)

            # Accept the connection
            await self.accept()

            # Start heartbeat task
            try:
                self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
            except Exception as e:
                logger.error(f"Failed to start heartbeat task: {str(e)}")

            # Notify about user presence
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "user_online",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "timestamp": timezone.now().isoformat(),
                },
            )

            # Update user's online status
            await self.update_user_status(True)

            logger.info(
                f"User {self.user.id} connected to one-to-one conversation {self.conversation_id}"
            )

        except Exception as e:
            logger.error(f"Error in one-to-one connect: {str(e)}", exc_info=True)
            await self.close()

    @database_sync_to_async
    def check_one_to_one_conversation_access(self):
        """Check if user has access to this one-to-one conversation"""
        try:
            conversation = OneToOneConversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.user.id).exists()
        except OneToOneConversation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking one-to-one conversation access: {str(e)}", exc_info=True)
            return False

    async def handle_new_message(self, data):
        """Handle a new one-to-one message event"""
        content = data.get("content", "").strip()
        conversation_id = self.conversation_id
        message_type = data.get("message_type", "text")
        metadata = data.get("metadata", {})
        media_id = data.get("media_id")

        if not content and not media_id:
            return

        # Create the one-to-one message in database
        message = await self.create_one_to_one_message(
            conversation_id, content, message_type, metadata, media_id
        )

        if message:
            # Prepare message data for WebSocket response
            message_data = {
                "id": str(message["id"]),
                "content": message["content"],
                "sender_id": str(message["sender_id"]),
                "sender_name": message["sender_name"],
                "conversation_id": str(conversation_id),
                "timestamp": message["timestamp"],
                "message_type": message_type,
                "media_url": message.get("media_url"),
                "metadata": metadata,
                "conversation_type": "one_to_one",
            }

            # Broadcast to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "chat.message",
                    "message": message_data,
                    "event": "new_message",
                },
            )

    @database_sync_to_async
    def create_one_to_one_message(
        self,
        conversation_id,
        content,
        message_type="text",
        metadata=None,
        media_id=None,
    ):
        """Create a new one-to-one message in the database"""
        try:
            if metadata is None:
                metadata = {}

            conversation = OneToOneConversation.objects.get(id=conversation_id)
            message = OneToOneMessage.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                message_type=message_type,
                metadata=metadata,
            )
            
            if media_id:
                from media_handler.models import MediaFile
                media = MediaFile.objects.get(id=media_id)
                message.media = media.file
                message.save()

            # Update conversation last_activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])

            # Prepare response
            result = {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender.username,
                "timestamp": message.timestamp.isoformat(),
            }

            # Add media URL if present
            if message.media:
                result["media_url"] = message.media.url

            return result

        except Exception as e:
            logger.error(f"Error creating one-to-one message: {str(e)}", exc_info=True)
            return None


class GroupChatConsumer(BaseWebSocketConsumer):
    """
    WebSocket consumer for handling group messaging.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_type = "group"

    async def connect(self):
        """Handle WebSocket connection for group chat"""
        try:
            # Get user and conversation ID
            self.user = self.scope["user"]
            self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
            self.conversation_group_name = f"group_{self.conversation_id}"
            self.user_group_name = f"user_{self.user.id}"

            # Setup heartbeat monitoring
            self.last_ping = timezone.now()
            self.heartbeat_interval = getattr(
                settings, "WEBSOCKET_HEARTBEAT_INTERVAL", 30
            )
            self.heartbeat_task = None

            # Check if user is anonymous
            if self.user.is_anonymous:
                logger.warning(
                    f"Anonymous user tried to connect to {self.conversation_group_name}"
                )
                await self.close()
                return

            # Validate user's access to the group conversation
            has_access = await self.check_group_conversation_access()
            if not has_access:
                logger.warning(
                    f"User {self.user.id} tried to access unauthorized group conversation {self.conversation_id}"
                )
                await self.close()
                return

            # Add to conversation group
            await self.channel_layer.group_add(
                self.conversation_group_name, self.channel_name
            )

            # Add to user-specific group for private notifications
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)

            # Accept the connection
            await self.accept()

            # Start heartbeat task
            try:
                self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
            except Exception as e:
                logger.error(f"Failed to start heartbeat task: {str(e)}")

            # Notify about user presence
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "user_online",
                    "user_id": str(self.user.id),
                    "username": self.user.username,
                    "timestamp": timezone.now().isoformat(),
                },
            )

            # Update user's online status
            await self.update_user_status(True)

            logger.info(
                f"User {self.user.id} connected to group conversation {self.conversation_id}"
            )

        except Exception as e:
            logger.error(f"Error in group connect: {str(e)}", exc_info=True)
            await self.close()

    @database_sync_to_async
    def check_group_conversation_access(self):
        """Check if user has access to this group conversation"""
        try:
            conversation = GroupConversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.user.id).exists()
        except GroupConversation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking group conversation access: {str(e)}", exc_info=True)
            return False

    async def handle_new_message(self, data):
        """Handle a new group message event"""
        content = data.get("content", "").strip()
        conversation_id = self.conversation_id
        message_type = data.get("message_type", "text")
        metadata = data.get("metadata", {})
        media_id = data.get("media_id")

        if not content and not media_id:
            return

        # Create the group message in database
        message = await self.create_group_message(
            conversation_id, content, message_type, metadata, media_id
        )

        if message:
            # Prepare message data for WebSocket response
            message_data = {
                "id": str(message["id"]),
                "content": message["content"],
                "sender_id": str(message["sender_id"]),
                "sender_name": message["sender_name"],
                "conversation_id": str(conversation_id),
                "timestamp": message["timestamp"],
                "message_type": message_type,
                "media_url": message.get("media_url"),
                "metadata": metadata,
                "conversation_type": "group",
            }

            # Broadcast to conversation group
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    "type": "chat.message",
                    "message": message_data,
                    "event": "new_message",
                },
            )

    @database_sync_to_async
    def create_group_message(
        self,
        conversation_id,
        content,
        message_type="text",
        metadata=None,
        media_id=None,
    ):
        """Create a new group message in the database"""
        try:
            if metadata is None:
                metadata = {}

            conversation = GroupConversation.objects.get(id=conversation_id)
            message = GroupMessage.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                message_type=message_type,
                metadata=metadata,
            )
            
            if media_id:
                from media_handler.models import MediaFile
                media = MediaFile.objects.get(id=media_id)
                message.media = media.file
                message.save()

            # Update conversation last_activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])

            # Prepare response
            result = {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender.username,
                "timestamp": message.timestamp.isoformat(),
            }

            # Add media URL if present
            if message.media:
                result["media_url"] = message.media.url

            return result

        except Exception as e:
            logger.error(f"Error creating group message: {str(e)}", exc_info=True)
            return None



30)# messaging/exceptions.py


class WebSocketAuthenticationError(Exception):
    """Exception raised when WebSocket authentication fails."""

    pass


class WebSocketConnectionError(Exception):
    """Exception raised when a WebSocket connection cannot be established."""

    pass


class WebSocketMessageError(Exception):
    """Exception raised when there's an error sending or processing WebSocket messages."""

    pass


class ConversationAccessError(Exception):
    """Exception raised when a user tries to access a conversation they aren't part of."""

    pass


class MessageDeliveryError(Exception):
    """Exception raised when a message cannot be delivered."""

    pass


class RateLimitExceededError(Exception):
    """Exception raised when a user exceeds rate limits for message sending."""

    pass

331)# messaging/middleware.py
from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.response import Response
from channels.layers import get_channel_layer
import logging
from django.utils import timezone
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import (
    TokenError,
    InvalidToken,
)  # Add this import
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


class MessageEncryptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY)

    def __call__(self, request):
        response = self.get_response(request)

        if isinstance(response, Response) and "messages" in response.data:
            response.data["messages"] = [
                self._encrypt_message(msg) for msg in response.data["messages"]
            ]
        return response

    def _encrypt_message(self, message):
        message["content"] = self.cipher.encrypt(message["content"].encode()).decode()
        return message


class RealTimeMiddleware:
    """Middleware to handle real-time updates for messaging actions"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.channel_layer = get_channel_layer()
        # Define conversation URL patterns for more robust path matching
        self.conversation_patterns = {
            "one_to_one": r"/api/messaging/one_to_one/(\d+)",
            "groups": r"/api/messaging/groups/(\d+)",
        }

    def __call__(self, request):
        response = self.get_response(request)

        try:
            # Skip if channel layer is not available
            if not self.channel_layer:
                return response

            # Check if this is a messaging action that needs real-time updates
            if self._should_send_update(request, response):
                self._send_websocket_update(request, response)
        except Exception as e:
            logger.error(f"Error in RealTimeMiddleware: {str(e)}", exc_info=True)

        return response

    def _should_send_update(self, request, response):
        """Determine if the request should trigger a real-time update"""
        # Only for messaging endpoints, certain methods, and successful responses
        is_messaging_path = request.path.startswith("/api/messaging/")
        is_modifying_method = request.method in ["POST", "PUT", "PATCH", "DELETE"]
        is_successful = 200 <= response.status_code < 300

        return is_messaging_path and is_modifying_method and is_successful

    def _extract_conversation_id(self, path):
        """Extract conversation ID from request path more reliably using regex"""
        import re

        try:
            # Try to match path against known conversation patterns
            for conv_type, pattern in self.conversation_patterns.items():
                match = re.search(pattern, path)
                if match:
                    conversation_id = match.group(1)
                    logger.debug(
                        f"Extracted conversation ID {conversation_id} from path {path} (type: {conv_type})"
                    )
                    return conversation_id

            # If no direct match, try to find any numeric ID that might be a conversation ID
            segments = path.strip("/").split("/")
            for i, segment in enumerate(segments):
                if segment in [
                    "conversation",
                    "conversations",
                    "messages",
                ] and i + 1 < len(segments):
                    potential_id = segments[i + 1]
                    if potential_id.isdigit():
                        logger.debug(
                            f"Found potential conversation ID {potential_id} from path {path}"
                        )
                        return potential_id

            logger.debug(f"Could not extract conversation ID from path: {path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting conversation ID: {str(e)}", exc_info=True)
            return None

    def _send_websocket_update(self, request, response):
        """Send WebSocket update for real-time messaging"""
        try:
            conversation_id = self._extract_conversation_id(request.path)
            if not conversation_id:
                return

            # Import the message delivery service
            from messaging.services.message_delivery import message_delivery_service

            # Determine action type based on method and endpoint
            if "message" in request.path.lower():
                if request.method == "POST":
                    action = "message_created"
                elif request.method in ["PUT", "PATCH"]:
                    action = "message_updated"
                elif request.method == "DELETE":
                    action = "message_deleted"
                else:
                    action = "message_action"
            else:
                action = "conversation_updated"

            # Prepare message data
            message_data = {
                "user_id": str(request.user.id),
                "username": request.user.username,
                "data": response.data if hasattr(response, "data") else {},
                "timestamp": timezone.now().isoformat(),
                "conversation_id": conversation_id,
            }

            # Use the unified service to send the update
            message_delivery_service.send_message_update(
                conversation_id=conversation_id,
                event_type=action,
                message_data=message_data,
                user_id=str(request.user.id),
            )

            logger.debug(
                f"Sent WebSocket update for {action} in conversation {conversation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {str(e)}", exc_info=True)


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            query_string = scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)
            token = query_params.get("token", [None])[0]

            if not token:
                logger.warning("No token provided in WebSocket connection")
                scope["user"] = AnonymousUser()
                return await super().__call__(scope, receive, send)

            user = await self.get_user_from_token(token)
            if not user:
                logger.warning("Invalid token or user not found")
                scope["user"] = AnonymousUser()
                return await super().__call__(scope, receive, send)

            scope["user"] = user
            return await super().__call__(scope, receive, send)

        except Exception as e:
            logger.error(f"WebSocket auth error: {str(e)}", exc_info=True)
            scope["user"] = AnonymousUser()
            return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            User = get_user_model()
            return User.objects.get(id=user_id)
        except (TokenError, InvalidToken, User.DoesNotExist) as e:
            logger.warning(f"Token validation failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in token validation: {str(e)}", exc_info=True
            )
            return None


class OnlineStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Update last activity time
            request.user.last_activity = timezone.now()
            request.user.save(update_fields=["last_activity"])
        return self.get_response(request)

34)# messaging/pagination.py
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from cryptography.fernet import Fernet
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MessagePagination(CursorPagination):
    """Base cursor pagination for messages"""

    page_size = 20
    ordering = "-timestamp"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                "total_count": self.page.paginator.count,
            }
        )


class EncryptedMessagePagination(MessagePagination):
    """Cursor pagination with content encryption"""

    def __init__(self):
        super().__init__()
        self.cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY)

    def get_paginated_response(self, data):
        try:
            # Encrypt message content
            encrypted_data = [
                {**msg, "content": self._encrypt_content(msg.get("content", ""))}
                for msg in data
            ]

            return super().get_paginated_response(encrypted_data)

        except Exception as e:
            logger.error(f"Error encrypting paginated data: {str(e)}", exc_info=True)
            return Response({"error": "Failed to process messages"}, status=500)

    def _encrypt_content(self, content):
        """Encrypt message content"""
        if not content:
            return ""
        try:
            return self.cipher.encrypt(content.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            return ""


class CustomMessagePagination(CursorPagination):
    """Custom cursor pagination for messages"""

    page_size = 50
    ordering = "-timestamp"
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        count = 0
        # Handle case where self.page is a list without paginator
        if hasattr(self, "page"):
            if hasattr(self.page, "paginator"):
                count = self.page.paginator.count
            elif isinstance(self.page, list):
                count = len(self.page)

        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "count": count,
                "results": data,
                "next_cursor": self.get_next_cursor(),
            }
        )

    def get_next_cursor(self):
        try:
            if (
                hasattr(self, "page")
                and self.page
                and hasattr(self.page, "has_next")
                and self.page.has_next
            ):
                last_item = self.page[-1]
                return str(last_item.id)
            elif (
                isinstance(getattr(self, "page", None), list)
                and len(self.page) >= self.page_size
            ):
                # If we have exactly page_size items, there might be more
                last_item = self.page[-1]
                return str(last_item.id)
            return None
        except Exception as e:
            logger.error(f"Error getting next cursor: {str(e)}")
            return None

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "next": {"type": "string", "format": "uri", "nullable": True},
                "previous": {"type": "string", "format": "uri", "nullable": True},
                "count": {"type": "integer"},
                "results": schema,
                "next_cursor": {"type": "string", "nullable": True},
            },
        }

35)# messaging/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsTherapist(BasePermission):
    """
    Custom permission to only allow therapists to access therapy-specific features
    """

    def has_permission(self, request, view):
        return (
            request.user
            and hasattr(request.user, "user_type")
            and request.user.user_type == "therapist"
        )


class IsParticipant(BasePermission):
    """
    Custom permission to only allow participants of a conversation to access it
    """

    def has_object_permission(self, request, view, obj):
        return request.user in obj.participants.all()


class IsModerator(BasePermission):
    """
    Custom permission to allow moderators to manage conversations
    """

    def has_permission(self, request, view):
        return (
            request.user
            and hasattr(request.user, "is_moderator")
            and request.user.is_moderator
        )


class CanSendMessage(BasePermission):
    """
    Custom permission to check if user can send messages in a conversation
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not obj:
            return False
        return request.user in obj.participants.all() and not getattr(
            request.user, "is_muted", False
        )


class IsParticipantOrModerator(permissions.BasePermission):
    """
    Permission to only allow participants or moderators of a conversation to access it.
    """

    def has_permission(self, request, view):
        # Allow all authenticated users for list/create
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Check if user is participant
        if hasattr(obj, "participants"):
            is_participant = obj.participants.filter(id=request.user.id).exists()

            # For safe methods (GET, HEAD, OPTIONS) being a participant is enough
            if request.method in permissions.SAFE_METHODS and is_participant:
                return True

            # For modify/delete methods, check if user is moderator (for group conversations)
            if hasattr(obj, "moderators"):
                is_moderator = obj.moderators.filter(id=request.user.id).exists()
                return is_moderator

            # For one-to-one conversations, being a participant is enough for all operations
            return is_participant

        # For message objects, check if user is participant in the conversation
        if hasattr(obj, "conversation"):
            if hasattr(obj.conversation, "participants"):
                is_participant = obj.conversation.participants.filter(
                    id=request.user.id
                ).exists()

                # For safe methods, being a participant is enough
                if request.method in permissions.SAFE_METHODS:
                    return is_participant

                # For modify/delete, check if user is sender or moderator
                is_sender = obj.sender == request.user

                # If group conversation, check if user is moderator
                if hasattr(obj.conversation, "moderators"):
                    is_moderator = obj.conversation.moderators.filter(
                        id=request.user.id
                    ).exists()
                    return is_sender or is_moderator

                # For one-to-one messages, only allow sender to modify
                return is_sender

        return False


class IsMessageSender(permissions.BasePermission):
    """
    Permission to only allow the sender of a message to modify it.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # For safe methods, check if user is participant in the conversation
        if request.method in permissions.SAFE_METHODS:
            if hasattr(obj, "conversation") and hasattr(
                obj.conversation, "participants"
            ):
                return obj.conversation.participants.filter(id=request.user.id).exists()

        # For modify/delete, check if user is the sender
        return obj.sender == request.user

36)# messaging/routing.py
from django.urls import path
from .consumers import OneToOneChatConsumer, GroupChatConsumer

websocket_urlpatterns = [
    # WebSocket URL for one-to-one conversations
    path("ws/one-to-one/<str:conversation_id>/", OneToOneChatConsumer.as_asgi()),
    # WebSocket URL for group conversations
    path("ws/group/<str:conversation_id>/", GroupChatConsumer.as_asgi()),
]

# Export the URL patterns for inclusion in the ASGI application
urlpatterns = websocket_urlpatterns

37)# messaging/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import logging

# Add new imports for WebSocket updates

from .models.one_to_one import OneToOneMessage
from .models.group import GroupMessage
from .models.base import BaseMessage

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=OneToOneMessage)
@receiver(post_delete, sender=GroupMessage)
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
        if hasattr(instance, "reactions"):
            cache_key = f"message_reactions_{instance.id}"

            if not created:
                # Update reactions cache when message is modified
                cache.set(cache_key, instance.reactions, timeout=3600)
            else:
                # Initialize empty reactions cache for new messages
                cache.set(cache_key, [], timeout=3600)

            # Get reactions from cache for validation
            cached_reactions = cache.get(cache_key)
            if cached_reactions is None:
                # If cache miss, repopulate from instance
                cache.set(cache_key, instance.reactions, timeout=3600)
                logger.info(f"Repopulated reactions cache for message {instance.id}")

    except Exception as e:
        logger.error(f"Error handling message reaction: {str(e)}", exc_info=True)

39)	# messaging/throttling.py
from rest_framework.throttling import UserRateThrottle
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class UserRateThrottle(UserRateThrottle):
    """
    Throttle for API requests by authenticated users.
    Default rate: 60/minute
    """

    scope = "user"
    rate = getattr(settings, "API_THROTTLE_RATE_USER", "60/minute")


class MessageRateThrottle(UserRateThrottle):
    """
    Stricter throttle for message creation.
    Default rate: 30/minute
    """

    scope = "message"
    rate = getattr(settings, "API_THROTTLE_RATE_MESSAGE", "30/minute")


class GroupMessageThrottle(UserRateThrottle):
    """
    Throttle for group messaging with reasonable limits.
    Default rate: 20/minute
    """

    scope = "group_message"
    rate = getattr(settings, "API_THROTTLE_RATE_GROUP_MESSAGE", "20/minute")


class ReadReceiptThrottle(UserRateThrottle):
    """
    Throttle for read receipts to prevent flooding.
    Default rate: 50/minute
    """

    scope = "read_receipt"
    rate = getattr(settings, "API_THROTTLE_RATE_READ_RECEIPT", "50/minute")


class TypingIndicatorThrottle(UserRateThrottle):
    """
    Throttle for typing indicators with a higher rate because they are sent frequently.
    Default rate: 20/10seconds
    """

    scope = "typing"
    rate = getattr(settings, "API_THROTTLE_RATE_TYPING", "20/10second")


class ReactionThrottle(UserRateThrottle):
    """
    Throttle for message reactions.
    Default rate: 40/minute
    """

    scope = "reaction"
    rate = getattr(settings, "API_THROTTLE_RATE_REACTION", "40/minute")


class BurstRateThrottle(UserRateThrottle):
    """
    More permissive throttle for burst operations.
    Default rate: 120/minute
    """

    scope = "burst"
    rate = getattr(settings, "API_THROTTLE_RATE_BURST", "120/minute")

40)# messaging/urls.py
from django.urls import path
from .views.one_to_one import OneToOneConversationViewSet, OneToOneMessageViewSet
from .views.group import GroupConversationViewSet, GroupMessageViewSet
from .views.offline import OfflineMessageSyncView
from messaging.views.all_conversations import AllConversationsView

urlpatterns = [
    # ==============================
    # One-to-One Conversation Endpoints
    # ==============================
    path(
        "one_to_one/",
        OneToOneConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="one_to_one_conversation_list",
    ),
    path(
        "one_to_one/<int:pk>/",
        OneToOneConversationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="one_to_one_conversation_detail",
    ),
    path(
        "one_to_one/<int:pk>/messages/",
        OneToOneConversationViewSet.as_view({"get": "messages"}),
        name="one_to_one_messages",
    ),
    path(
        "one_to_one/<int:pk>/search/",
        OneToOneConversationViewSet.as_view({"get": "search"}),
        name="one_to_one_search",
    ),
    # ==============================
    # One-to-One Message Endpoints
    # ==============================
    path(
        "one_to_one/messages/",
        OneToOneMessageViewSet.as_view({"get": "list", "post": "create"}),
        name="one_to_one_message_list",
    ),
    path(
        "one_to_one/messages/<int:pk>/",
        OneToOneMessageViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="one_to_one_message_detail",
    ),
    # ==============================
    # Group Conversation Endpoints
    # ==============================
    path(
        "groups/",
        GroupConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="group_conversation_list",
    ),
    path(
        "groups/<int:pk>/",
        GroupConversationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="group_conversation_detail",
    ),
    path(
        "groups/<int:pk>/add_moderator/",
        GroupConversationViewSet.as_view({"post": "add_moderator"}),
        name="group_add_moderator",
    ),
    path(
        "groups/<int:pk>/moderators/",
        GroupConversationViewSet.as_view({"get": "moderators"}),
        name="group_moderators",
    ),
    path(
        "groups/<int:pk>/add_participant/",
        GroupConversationViewSet.as_view({"post": "add_participant"}),
        name="group_add_participant",
    ),
    path(
        "groups/<int:pk>/remove_participant/",
        GroupConversationViewSet.as_view({"post": "remove_participant"}),
        name="group_remove_participant",
    ),
    path(
        "groups/<int:pk>/pin_message/",
        GroupConversationViewSet.as_view({"post": "pin_message"}),
        name="group_pin_message",
    ),
    path(
        "groups/search_messages/",
        GroupConversationViewSet.as_view({"get": "search_messages"}),
        name="group_search_messages",
    ),
    path(
        "groups/search_groups/",
        GroupConversationViewSet.as_view({"get": "search_groups"}),
        name="group_search_groups",
    ),
    path(
        "groups/search_all/",
        GroupConversationViewSet.as_view({"get": "search_all"}),
        name="group_search_all",
    ),
    # ==============================
    # Group Message Endpoints
    # ==============================
    path(
        "groups/messages/",
        GroupMessageViewSet.as_view({"get": "list", "post": "create"}),
        name="group_message_list",
    ),
    path(
        "groups/messages/<int:pk>/",
        GroupMessageViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="group_message_detail",
    ),
    # ==============================
    # Offline Messaging Sync Endpoint
    # ==============================
    path(
        "offline/messages/", OfflineMessageSyncView.as_view(), name="offline_messages"
    ),
    # ==============================
    # All Conversations Endpoint
    # ==============================
    path("all/", AllConversationsView.as_view(), name="all_conversations"),
]
**Messaging Caching System Report**
*This backend is designed to support a React Native client application.*

---

## 1. Overview

The messaging subsystem employs a multi-layered cache architecture to optimize performance, reduce database load, and enable offline support for React Native users. Core components include:

* **Cache Manager** (`MessagingCacheManager`)
* **Offline Message Handler** (`OfflineMessageHandler`)
* **Serialization Utilities** (`MessageSerializer`, `CacheJSONEncoder`)
* **Service Layer Cache** (`MessageServiceCache`)
* **Signal Handlers** (Django signals for cache invalidation and updates)
* **Viewset Mixins** (edit history & reactions)
* **Data Models** (base, group, one-to-one)
* **Connection Manager** (WebSocket lifecycle)&#x20;

---

## 2. Cache Manager

* Central singleton (`message_cache`) using Django’s cache framework (default timeout 1 hr)
* Builds keys via `_build_key(…)`, e.g. `"msg:<id>"`, `"conv:<id>:messages"`
* CRUD operations for messages, conversations, participants, reactions, typing status
* Offline queue stored under prefix `"offline_queue_<user_id>"` with 24 hr TTL&#x20;

---

## 3. Offline Message Handler

* Queues messages created while offline and processes them upon reconnection
* Persists to DB within an atomic transaction, resolves conflicts, updates cache
* Tracks success, error, and already-synced counts
* Clears synced entries post-delivery&#x20;

---

## 4. Serialization Utilities

* **CacheJSONEncoder** handles `datetime`, `set`, `bytes` for JSON caching
* **MessageSerializer** converts message and conversation model instances to cacheable dicts, preserving sender info, edit history, reactions, metadata; rehydrates via `from_json()`&#x20;

---

## 5. Service Layer Cache

* **MessageServiceCache** wraps `message_cache` and `offline_handler`
* Provides high-level APIs:

  * `get_message()`, `get_messages_for_conversation()` with DB fallback
  * `get_conversation()`, `get_user_conversations()`
  * `queue_offline_message()`, `process_offline_messages()`
  * `save_message()`, `update_message()`, `invalidate_message()`&#x20;

---

## 6. Signal Handlers

* **post\_save** on `OneToOneMessage`/`GroupMessage` to cache messages and update conversation activity
* **pre\_save** to track edits/reactions for history caching
* **post\_delete** to invalidate message cache and refresh conversation cache
* **post\_save**/`post_delete` on conversations to maintain user-conversation lists and clear stale cache&#x20;

---

## 7. Viewset Mixins

* **EditHistoryMixin** exposes a `GET /messages/{id}/edit_history/` endpoint
* **ReactionMixin** provides `add-reaction`, `remove-reaction`, `GET /reactions/` actions within DRF viewsets&#x20;

---

## 8. Data Models

### 8.1 Base Classes

* **BaseConversation**: participants M2M, `last_activity`, `archived` flags, validation for participant count
* **BaseMessage**: sender FK, content, timestamp, `read_by` M2M, JSONField `reactions`, soft-delete, edit tracking, metadata, edit history&#x20;

### 8.2 Group

* **GroupConversation**: adds `name`, `description`, `moderators`, `is_private`
* **GroupMessage**: FK to `GroupConversation`, optional media upload with extension validation&#x20;

### 8.3 One-to-One

* **OneToOneConversation**: enforced exactly two participants via through model and m2m signals
* **OneToOneMessage**: extends `BaseMessage` with ArrayField `edit_history`, optional media&#x20;

---

## 9. Serializers

* **GroupConversationSerializer** and **GroupMessageSerializer** for full REST API, including participant counts, last message, media URLs
* **OneToOneConversationSerializer/OneToOneMessageSerializer** handling dynamic fields based on HTTP method, user-type validation (patient/therapist), media URL resolution&#x20;

---

## 10. Connection Manager

* Tracks active WebSocket connections for React Native clients: registration, activity updates, cleanup of stale connections after threshold (default 120 s)
* Integrates with Django Channels layer&#x20;

---

## 11. Integration with React Native

* All endpoints and WebSocket channels are designed to serve a React Native front end
* JSON-based cache payloads optimize mobile data usage and offline resilience
* Offline queue enables seamless composition and delivery of messages when network connectivity is restored

---

## 12. Conclusion

This comprehensive caching architecture ensures high performance, consistency, and offline capability for a React Native messaging client. Each layer—from low-level cache operations to service-level APIs and real-time connection management—works together to provide a smooth, reliable user experience.

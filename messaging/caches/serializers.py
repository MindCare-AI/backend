# messaging/caches/serializers.py
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

            # Add chatbot-specific fields
            if hasattr(message, "is_bot"):
                data["is_bot"] = message.is_bot

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
                except:
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

            # Add chatbot-specific fields
            if hasattr(conversation, "user"):
                data["user_id"] = conversation.user.id

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

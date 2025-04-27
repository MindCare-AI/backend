from django.core.cache import cache
from django.conf import settings

# Cache timeout settings (in seconds)
REACTION_CACHE_TIMEOUT = getattr(settings, 'REACTION_CACHE_TIMEOUT', 3600)  # 1 hour
EDIT_HISTORY_CACHE_TIMEOUT = getattr(settings, 'EDIT_HISTORY_CACHE_TIMEOUT', 3600 * 24)  # 24 hours
PARTICIPANTS_CACHE_TIMEOUT = getattr(settings, 'PARTICIPANTS_CACHE_TIMEOUT', 3600)  # 1 hour
READ_RECEIPTS_CACHE_TIMEOUT = getattr(settings, 'READ_RECEIPTS_CACHE_TIMEOUT', 1800)  # 30 minutes

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
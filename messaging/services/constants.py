# messaging/services/constants.py
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

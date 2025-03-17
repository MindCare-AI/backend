# messaging/services/exceptions.py
class ChatbotError(Exception):
    """Base exception for chatbot-related errors"""

    pass


class ChatbotConfigError(ChatbotError):
    """Raised when there's a configuration error"""

    pass


class ChatbotAPIError(ChatbotError):
    """Raised when there's an API-related error"""

    pass

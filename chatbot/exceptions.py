# chatbot/exceptions.py
class ChatbotError(Exception):
    """Base exception for chatbot-related errors"""

    pass


class ChatbotConfigError(ChatbotError):
    """Error related to chatbot configuration"""

    pass


class ChatbotAPIError(ChatbotError):
    """Error related to chatbot API calls"""

    pass

#chatbot/apps.py
from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot"

    def ready(self):
        """Initialize app settings and signals"""
        try:
            from django.conf import settings

            settings.CHATBOT_SETTINGS
        except AttributeError:
            # Set default settings if not configured
            settings.CHATBOT_SETTINGS = {
                "MAX_RETRIES": 3,
                "RESPONSE_TIMEOUT": 30,
                "MAX_HISTORY_MESSAGES": 5,
            }

# chatbot/apps.py
from django.apps import AppConfig
import logging
import os

logger = logging.getLogger(__name__)


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
            from django.conf import settings

            settings.CHATBOT_SETTINGS = {
                "MAX_RETRIES": 3,
                "RESPONSE_TIMEOUT": 30,
                "MAX_HISTORY_MESSAGES": 5,
            }

        # Configure RAG settings
        try:
            # Set default RAG settings if not configured
            if not hasattr(settings, "RAG_SETTINGS"):
                settings.RAG_SETTINGS = {
                    "EMBEDDING_MODEL": os.getenv(
                        "EMBEDDING_MODEL", "nomic-embed-text:latest"
                    ),
                    "EMBEDDING_DIMENSION": int(os.getenv("EMBEDDING_DIMENSION", 384)),
                    "SIMILARITY_THRESHOLD": float(
                        os.getenv("SIMILARITY_THRESHOLD", 0.65)
                    ),
                    "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                    "OLLAMA_NUM_GPU": int(os.getenv("OLLAMA_NUM_GPU", 50)),
                    "CHUNK_SIZE": int(os.getenv("CHUNK_SIZE", 1000)),
                    "CHUNK_OVERLAP": int(os.getenv("CHUNK_OVERLAP", 200)),
                }
                logger.info("RAG settings initialized with defaults")
        except Exception as e:
            logger.error(f"Error initializing RAG settings: {str(e)}")

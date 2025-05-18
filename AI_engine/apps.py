# AI_engine/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AIEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "AI_engine"

    def ready(self):
        """Initialize AI Engine components"""
        try:
            # Initialize AI services
            from .services.ai_analysis import ai_service

            # Verify Ollama connection
            if not ai_service.base_url:
                logger.error("Ollama URL not configured")
                return

            # Verify Gemini configuration in settings
            from django.conf import settings

            if not hasattr(settings, "GEMINI_API_KEY") or not settings.GEMINI_API_KEY:
                logger.error("Gemini API key not configured")
                return

            logger.info("AI Engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AI Engine: {str(e)}")
            return False

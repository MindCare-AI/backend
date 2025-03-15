# messaging/services/chatbot.py
import requests
from typing import List, Dict
from django.conf import settings
import logging
from .exceptions import ChatbotError
from .constants import THERAPEUTIC_GUIDELINES

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions"""

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ChatbotError("Gemini API key not configured")

        self.api_key = settings.GEMINI_API_KEY
        self.api_url = settings.GEMINI_API_URL
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]

    def get_response(self, message: str, history: List[Dict]) -> Dict[str, any]:
        """Get chatbot response with error handling and retries"""
        try:
            # Validate input
            if not self._validate_input(message, history):
                return self._error_response("Invalid input parameters")

            # Build prompt with context
            prompt = self._build_prompt(message, history)

            # Make API request with retries
            for attempt in range(self.max_retries):
                try:
                    return self._make_api_request(prompt)
                except requests.RequestException as e:
                    if attempt == self.max_retries - 1:
                        logger.error(
                            f"API request failed after {self.max_retries} attempts: {str(e)}"
                        )
                        return self._error_response("Service temporarily unavailable")
                    continue

        except Exception as e:
            logger.error(f"Chatbot error: {str(e)}")
            return self._error_response("Internal service error")

    def _validate_input(self, message: str, history: List[Dict]) -> bool:
        """Validate input parameters"""
        if not isinstance(message, str) or not message.strip():
            return False

        if not isinstance(history, list):
            return False

        # Validate history format
        return all(
            isinstance(msg, dict) and "sender" in msg and "content" in msg
            for msg in history[-settings.CHATBOT_SETTINGS["MAX_HISTORY_MESSAGES"] :]
        )

    def _build_prompt(self, message: str, history: List[Dict]) -> str:
        """Build prompt with context and history"""
        # Format recent history
        history_str = "\n".join(
            f"{msg['sender']}: {msg['content']}"
            for msg in history[-settings.CHATBOT_SETTINGS["MAX_HISTORY_MESSAGES"] :]
        )

        return f"""Context: {THERAPEUTIC_GUIDELINES}

History:
{history_str}

User: {message}
Samantha:"""

    def _make_api_request(self, prompt: str) -> Dict[str, any]:
        """Make API request with error handling"""
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        response = requests.post(
            f"{self.api_url}?key={self.api_key}", json=payload, timeout=self.timeout
        )
        response.raise_for_status()

        data = response.json()
        if "candidates" not in data or not data["candidates"]:
            raise ChatbotError("Invalid API response format")

        return {
            "success": True,
            "response": data["candidates"][0]["content"]["parts"][0]["text"].strip(),
        }

    def _error_response(self, message: str) -> Dict[str, any]:
        """Format error response"""
        return {
            "success": False,
            "error": message,
            "response": "I'm having trouble responding right now. Please try again later.",
        }


# Create singleton instance
chatbot_service = ChatbotService()

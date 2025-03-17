# messaging/services/chatbot.py
import requests
from typing import List, Dict
from django.conf import settings
import logging
from .exceptions import ChatbotError

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions"""

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ChatbotError("Gemini API key not configured")

        self.api_key = settings.GEMINI_API_KEY
        # Updated API URL and model name
        self.api_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]
        self.max_history = settings.CHATBOT_SETTINGS.get("MAX_HISTORY_MESSAGES", 5)

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
        """Validate input parameters with improved checks"""
        if not isinstance(message, str) or not message.strip():
            logger.error("Invalid message format or empty message")
            return False

        if not isinstance(history, list):
            logger.error("History must be a list")
            return False

        # Validate each message in history
        for msg in history:
            if not isinstance(msg, dict):
                logger.error(f"Invalid history message format: {msg}")
                return False
            if not all(key in msg for key in ("content", "is_bot")):
                logger.error(f"Missing required fields in history message: {msg}")
                return False

        return True

    def _build_prompt(self, message: str, history: List[Dict]) -> str:
        """Build enhanced prompt for the chatbot with structured history and empathetic tone"""

        # Filter and format valid history entries
        valid_history = []
        for msg in history[-self.max_history :]:  # Keep recent exchanges only
            try:
                sender = "Samantha" if msg.get("is_bot") else "User"
                content = msg.get("content", "").strip()
                if content:
                    valid_history.append(f"{sender}: {content}")
            except Exception as e:
                logger.warning(f"Error processing history message: {e}")
                continue

        # Build enhanced context-aware prompt
        prompt = f"""
You are **Samantha**, an AI-powered **mental health support assistant** designed to provide **empathetic, supportive, and encouraging conversations**.  
You are **not a doctor or therapist**, but you can offer **comfort, guidance, and coping strategies** using evidence-based therapeutic techniques like **CBT, DBT, and mindfulness**.  

### **Guidelines for Responses:**
- Always be **warm, non-judgmental, and encouraging**.
- Use **active listening** and acknowledge emotions.
- Offer **practical coping strategies** (e.g., deep breathing, journaling).
- If a user expresses distress, suggest **self-care techniques** and encourage **seeking professional help** if needed.
- Do **not** diagnose or provide medical advice.

### **Conversation History:**
{chr(10).join(valid_history)}

### **Current User Message:**
User: {message.strip()}
Samantha: 
"""

        logger.debug(f"Built prompt with {len(valid_history)} history messages")
        return prompt

    def _make_api_request(self, prompt: str) -> Dict[str, any]:
        """Make API request with enhanced error handling and debugging"""
        try:
            debug_url = f"{self.api_url}?key=***"
            logger.debug(f"Making API request to: {debug_url}")
            logger.debug(f"Prompt length: {len(prompt)} characters")

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 1024,
                },
            }

            try:
                response = requests.post(
                    f"{self.api_url}",  # Remove key from URL
                    json=payload,
                    timeout=self.timeout,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "MindCare-Chatbot/1.0",
                        "x-goog-api-key": self.api_key,  # Add API key as header
                    },
                )

                # Log response details for debugging
                logger.debug(f"API Response Status: {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"API Error Response: {response.text}")

                # Handle specific error cases
                if response.status_code == 404:
                    logger.error("API endpoint not found - check API URL")
                    return self._error_response("Invalid API configuration")

                if response.status_code == 401:
                    logger.error("API Authentication failed - check API key")
                    return self._error_response("API authentication failed")

                if response.status_code == 429:
                    logger.warning("API rate limit exceeded")
                    return self._error_response("Service is currently busy")

                response.raise_for_status()

                data = response.json()
                if "candidates" not in data or not data["candidates"]:
                    logger.error(f"Invalid API response format: {data}")
                    return self._error_response("Unexpected API response format")

                response_text = data["candidates"][0]["content"]["parts"][0][
                    "text"
                ].strip()
                logger.info(
                    f"Successfully got response of {len(response_text)} characters"
                )

                return {
                    "success": True,
                    "response": response_text,
                }

            except requests.exceptions.Timeout:
                logger.error(f"API request timed out after {self.timeout}s")
                return self._error_response("Request timed out")

            except requests.exceptions.SSLError:
                logger.error("SSL verification failed")
                return self._error_response("Connection security error")

            except requests.exceptions.ConnectionError:
                logger.error(f"Connection failed to {self.api_url}")
                return self._error_response("Could not connect to service")

        except Exception as e:
            logger.exception(f"Unexpected error in API request: {str(e)}")
            return self._error_response("Internal service error")

    def _error_response(self, message: str) -> Dict[str, any]:
        """Format error response"""
        return {
            "success": False,
            "error": message,
            "response": "I'm having trouble responding right now. Please try again later.",
        }


# Create singleton instance
chatbot_service = ChatbotService()

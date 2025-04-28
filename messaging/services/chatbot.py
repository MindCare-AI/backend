"""Chatbot service using Google's Gemini API"""

import logging
import requests
from django.conf import settings
from typing import Dict, Any
from AI_engine.services import ai_service

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions using Gemini"""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.base_url = settings.GEMINI_API_URL
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.history_limit = settings.CHATBOT_SETTINGS["MAX_HISTORY_MESSAGES"]

    def get_response(
        self, user, message: str, conversation_history: list = None
    ) -> Dict[str, any]:
        """Get response from Gemini with user context and AI analysis"""
        try:
            # Get AI analysis from Ollama
            user_analysis = ai_service.analyze_user_data(user)

            # Prepare context with user info and AI analysis
            context = self._build_context(user, user_analysis)

            # Build the complete prompt
            prompt = self._build_prompt(message, context, conversation_history)

            # Make request to Gemini API
            response = self._make_api_request(prompt)
            if not response.get("success"):
                return response

            return {
                "success": True,
                "response": response["response"],
                "context_used": context,
                "analysis": user_analysis,
            }

        except Exception as e:
            logger.error(f"Error in chatbot response: {str(e)}")
            return self._error_response("Internal service error")

    def _build_context(self, user, analysis: Dict) -> Dict[str, Any]:
        """Build context including user info and AI analysis"""
        context = {
            "user_name": user.get_full_name() or user.username,
            "user_type": user.user_type,
            "current_mood": None,
            "recent_activities": [],
            "topics_of_concern": [],
            "risk_factors": {},
            "suggested_activities": [],
        }

        if analysis:
            context.update(
                {
                    "mood_score": analysis.get("mood_score", 0),
                    "sentiment_score": analysis.get("sentiment_score", 0),
                    "dominant_emotions": analysis.get("dominant_emotions", []),
                    "topics_of_concern": analysis.get("topics_of_concern", []),
                    "risk_factors": analysis.get("risk_factors", {}),
                    "suggested_activities": analysis.get("suggested_activities", []),
                }
            )

        return context

    def _build_prompt(self, message: str, context: Dict, history: list = None) -> str:
        """Build prompt for Gemini with context"""
        prompt = f"""You are MindCare AI, a therapeutic chatbot assistant. You are speaking with {context['user_name']}.

User Context:
- Name: {context['user_name']}
- Type: {context['user_type']}
- Current Mood Score: {context.get('mood_score', 'Unknown')}
- Dominant Emotions: {', '.join(context.get('dominant_emotions', ['Unknown']))}
- Topics of Concern: {', '.join(context.get('topics_of_concern', []))}
- Suggested Activities: {', '.join(context.get('suggested_activities', []))}

Recent conversation history:
{self._format_history(history) if history else 'No recent history'}

Remember to:
1. Be empathetic and supportive
2. Maintain a professional therapeutic relationship
3. Encourage positive coping strategies
4. Reference the user's name naturally in responses
5. Consider their current emotional state in your responses

User's message: {message}"""

        return prompt

    def _format_history(self, history: list) -> str:
        """Format conversation history for context"""
        if not history:
            return ""

        formatted = []
        for msg in history[-self.history_limit :]:
            sender = "User" if not msg.get("is_bot") else "Assistant"
            formatted.append(f"{sender}: {msg.get('content', '')}")

        return "\n".join(formatted)

    def _make_api_request(self, prompt: str) -> Dict[str, any]:
        """Make request to Gemini API"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {"contents": [{"parts": [{"text": prompt}]}]}

            response = requests.post(
                self.base_url, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result["candidates"][0]["content"]["parts"][0]["text"],
                }
            else:
                logger.error(f"Gemini API error: {response.status_code}")
                return self._error_response("API request failed")

        except requests.exceptions.Timeout:
            logger.error("Gemini API timeout")
            return self._error_response("Request timed out")
        except Exception as e:
            logger.error(f"Error in Gemini API request: {str(e)}")
            return self._error_response("API request failed")

    def _error_response(self, message: str) -> Dict[str, any]:
        """Format error response"""
        return {
            "success": False,
            "error": message,
            "response": "I'm having trouble responding right now. Please try again later.",
        }


# Create singleton instance
chatbot_service = ChatbotService()

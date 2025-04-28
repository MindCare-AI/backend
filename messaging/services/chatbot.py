"""Chatbot service using Google's Gemini API"""

import logging
import requests
import re
from django.conf import settings
from typing import Dict, Any, List, Tuple
from AI_engine.services import ai_service

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions using Gemini"""

    # Add harmful content categories
    SENSITIVE_CONTENT_CATEGORIES = [
        "hate_speech", "self_harm", "violence", "sexual_content",
        "harassment", "discrimination", "dangerous_content"
    ]

    def __init__(self):
        # Clean the API key by stripping whitespace and quotes
        raw_api_key = settings.GEMINI_API_KEY
        if isinstance(raw_api_key, str):
            self.api_key = raw_api_key.strip().replace('"', '').replace("'", "")
            logger.debug(f"API key initialized. Length: {len(self.api_key)}")
        else:
            self.api_key = None
            logger.error("GEMINI_API_KEY is not a string or is missing")
            
        # Update to use Gemini 2.0 Flash model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.history_limit = settings.CHATBOT_SETTINGS["MAX_HISTORY_MESSAGES"]

    def get_response(
        self, user, message: str, conversation_history: list = None
    ) -> Dict[str, any]:
        """Get response from Gemini with user context and AI analysis"""
        try:
            # Check for harmful content first
            content_check = self._check_content_safety(message)
            if content_check["is_harmful"]:
                logger.warning(f"User {user.id} sent harmful content: {content_check['category']}")
                return self._handle_harmful_content(user, message, content_check["category"])
            
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
                "user_id": user.id,  # Add the user ID to the response
            }

        except Exception as e:
            logger.error(f"Error in chatbot response: {str(e)}")
            return self._error_response("Internal service error")
            
    def _check_content_safety(self, message: str) -> Dict[str, Any]:
        """
        Check if message contains harmful content
        Returns: Dict with is_harmful flag and category if harmful
        """
        result = {"is_harmful": False, "category": None, "confidence": 0.0}
        
        # Keywords for different categories of harmful content
        harmful_patterns = {
            "hate_speech": [r'\bhate\s+(\w+)\b', r'\bkill\s+(\w+)\b', r'death to', r'\bnot human', 
                         r'\b(hate|hating|despise|detest)\s+(black|white|asian|hispanic|gay|lesbian|trans)',
                         r'\b(jews|muslims|christians|blacks|whites|asians)\s+(are|should)'],
            "self_harm": [r'\bsuicide\b', r'\bkill myself\b', r'\bwant to die\b', r'\bend my life\b'],
            "violence": [r'\bshoot\b', r'\bmurder\b', r'\bbomb\b', r'\bterror\b', r'\battack\b'],
            "sexual_content": [r'\bporn\b', r'\bchild.*sex', r'\bsex\b'],
            "discrimination": [r'\bsuperior\b', r'\binferior race\b', r'\bsubhuman\b']
        }
        
        # Check each category
        for category, patterns in harmful_patterns.items():
            for pattern in patterns:
                matches = re.search(pattern, message.lower())
                if matches:
                    result["is_harmful"] = True
                    result["category"] = category
                    result["confidence"] = 0.85  # Simple confidence value
                    result["match"] = matches.group(0)
                    break
            if result["is_harmful"]:
                break
                
        return result
        
    def _handle_harmful_content(self, user, message: str, category: str) -> Dict[str, Any]:
        """Generate therapeutic response for harmful content"""
        user_name = user.get_full_name() or user.username
        
        # Create specialized prompt for handling harmful content
        prompt = f"""You are MindCare AI, a therapeutic chatbot assistant. The user {user_name} has expressed potentially harmful content 
related to {category}. Your response must:

1. Remain calm, professional and compassionate
2. Acknowledge their feelings without agreeing with harmful views
3. Gently redirect the conversation toward exploring underlying emotions
4. Offer support and perspective
5. Avoid judgment while maintaining clear ethical boundaries
6. Do not repeat or quote the exact harmful statement back to them
7. Address them by name ({user_name}) to maintain personal connection
8. Provide a therapeutic perspective that shows empathy while discouraging harmful attitudes

User message category: {category}
"""

        # Make request to Gemini API with safety prompt
        response = self._make_api_request(prompt)
        
        if not response.get("success"):
            # Fallback response if API call fails
            return {
                "success": True,
                "response": f"I understand you're expressing strong feelings, {user_name}. While I'm here to support you, I'd like to explore what's behind these thoughts in a way that's constructive and helpful for your wellbeing. Could you tell me more about what you're experiencing right now?",
                "context_used": {"user_name": user_name},
                "analysis": self._create_default_analysis(),
                "user_id": user.id,
                "flagged_content": True,
                "category": category
            }
        
        return {
            "success": True,
            "response": response["response"],
            "context_used": {"user_name": user_name},
            "analysis": self._create_default_analysis(),
            "user_id": user.id,
            "flagged_content": True,
            "category": category
        }
    
    def _create_default_analysis(self) -> Dict:
        """Create a default analysis when analysis fails"""
        return {
            "mood_score": 0,
            "sentiment_score": 0,
            "emotions": ["neutral"],
            "topics": ["general"],
            "activities": ["relaxation"],
            "risks": {"general": "low"},
            "improvements": {"overall": 0},
            "needs_attention": False,
        }

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

Therapeutic Guidelines:
1. Be empathetic and supportive while maintaining ethical boundaries
2. Maintain a professional therapeutic relationship
3. Encourage positive coping strategies
4. Reference the user's name naturally in responses
5. Consider their current emotional state in your responses
6. Do not endorse or normalize any harmful viewpoints, including hate speech, discrimination, or harmful behaviors
7. Gently redirect harmful discussions toward exploring underlying emotions
8. Respond to sensitive topics with care and professionalism
9. Always prioritize user wellbeing and mental health

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
            if not self.api_key:
                logger.error("Missing Gemini API key")
                return self._error_response("API key configuration error")
                
            # Log API request details (without the full API key)
            logger.debug(f"Making request to {self.base_url}")
            logger.debug(f"API key starts with: {self.api_key[:4]}...{self.api_key[-4:] if len(self.api_key) > 8 else ''}")
            logger.debug(f"API key length: {len(self.api_key)}")
            
            # Construct the URL with API key as query parameter
            url = f"{self.base_url}?key={self.api_key}"
            
            # Set headers for the request
            headers = {
                "Content-Type": "application/json"
            }

            # Format the payload according to Gemini API requirements
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )

            # Log response status and details
            logger.debug(f"Gemini API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result["candidates"][0]["content"]["parts"][0]["text"],
                }
            elif response.status_code == 401:
                logger.error(f"Gemini API authentication error: Invalid API key")
                logger.error(f"Response details: {response.text}")
                return self._error_response("API authentication failed - check your API key")
            else:
                logger.error(f"Gemini API error: {response.status_code}")
                logger.error(f"Response details: {response.text}")
                return self._error_response(f"API request failed with status {response.status_code}")

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

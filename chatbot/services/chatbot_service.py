"""Chatbot service using Gemini for AI model inference"""

from typing import Dict, Any
import logging
from django.conf import settings
import re
import requests
from django.utils import timezone
from datetime import timedelta
from AI_engine.services.conversation_summary import conversation_summary_service
from journal.models import JournalEntry
from mood.models import MoodLog
from ..exceptions import ChatbotAPIError

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions using Google's Gemini API"""

    SENSITIVE_CONTENT_CATEGORIES = [
        "hate_speech",
        "self_harm",
        "violence",
        "sexual_content",
        "harassment",
        "discrimination",
        "dangerous_content",
    ]

    def __init__(self):
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        self.api_key = settings.GEMINI_API_KEY
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.history_limit = 6  # Limit to only 6 most recent messages
        self.journal_limit = getattr(settings, "CHATBOT_JOURNAL_LIMIT", 5)
        self.mood_limit = getattr(settings, "CHATBOT_MOOD_LIMIT", 10)
        self.lookback_days = getattr(settings, "CHATBOT_LOOKBACK_DAYS", 30)

    def get_response(
        self,
        user,
        message: str,
        conversation_id: str,
        conversation_history: list = None,
    ) -> Dict[str, any]:
        """Get response from Gemini with user context and AI analysis"""
        try:
            # Check message content safety
            safety_check = self._check_content_safety(message)
            if safety_check["is_harmful"]:
                return self._handle_harmful_content(
                    user, message, safety_check["category"]
                )

            # Get user's journal entries and mood data
            user_data = self._get_user_data(user)

            # Ensure conversation_history is limited and get summary of older messages
            conversation_context = self._prepare_conversation_context(
                user, conversation_id, conversation_history
            )

            # Build prompt with context including conversation summary, journal and mood data
            prompt = self._build_prompt(message, conversation_context, user_data, user)

            # Make request to Gemini API
            try:
                response = self._call_gemini_api(prompt)

                # After getting a response, check if we should generate a new summary
                self._check_and_update_conversation_summary(
                    user, conversation_id, conversation_history
                )

                return {
                    "content": response["text"],
                    "metadata": response.get("metadata", {}),
                }
            except Exception as e:
                logger.error(f"Gemini API error: {str(e)}")
                raise ChatbotAPIError(f"Gemini API error: {str(e)}")

        except Exception as e:
            logger.error(f"Error getting chatbot response: {str(e)}")
            return self._error_response(str(e))

    def _call_gemini_api(self, prompt: str) -> Dict[str, Any]:
        """Make a request to the Gemini API"""
        try:
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            }

            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                    },
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024,
                },
            }

            response = requests.post(
                self.api_url, headers=headers, json=data, timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                # Extract the actual text response from Gemini's response structure
                response_text = result["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "text": response_text,
                    "metadata": {"model": "gemini-pro", "finish_reason": "stop"},
                }
            else:
                logger.error(
                    f"Gemini API request failed with status {response.status_code}: {response.text}"
                )
                raise ChatbotAPIError(
                    f"Gemini API request failed with status {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API request error: {str(e)}")
            raise ChatbotAPIError(f"Gemini API request error: {str(e)}")

    def _check_content_safety(self, message: str) -> Dict[str, Any]:
        """
        Check if message contains harmful content
        Returns: Dict with is_harmful flag and category if harmful
        """
        result = {"is_harmful": False, "category": None, "confidence": 0.0}

        # Keywords for different categories of harmful content
        harmful_patterns = {
            "hate_speech": [
                r"\bhate\s+(\w+)\b",
                r"\bkill\s+(\w+)\b",
                r"death to",
                r"\bnot human",
                r"\b(hate|hating|despise|detest)\s+(black|white|asian|hispanic|gay|lesbian|trans)",
                r"\b(jews|muslims|christians|blacks|whites|asians)\s+(are|should)",
            ],
            "self_harm": [
                r"\bsuicide\b",
                r"\bkill myself\b",
                r"\bwant to die\b",
                r"\bend my life\b",
            ],
            "violence": [
                r"\bshoot\b",
                r"\bmurder\b",
                r"\bbomb\b",
                r"\bterror\b",
                r"\battack\b",
            ],
            "sexual_content": [r"\bporn\b", r"\bchild.*sex", r"\bsex\b"],
            "discrimination": [r"\bsuperior\b", r"\binferior race\b", r"\bsubhuman\b"],
        }

        # Check each category
        for category, patterns in harmful_patterns.items():
            for pattern in patterns:
                if any(re.search(p, message.lower()) for p in patterns):
                    result["is_harmful"] = True
                    result["category"] = category
                    result["confidence"] = 0.9
                    return result

        return result

    def _handle_harmful_content(
        self, user, message: str, category: str
    ) -> Dict[str, Any]:
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
        try:
            response = self._call_gemini_api(prompt)
            return {
                "content": response["text"],
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            logger.error(f"Error handling harmful content: {str(e)}")
            return self._error_response("Unable to process harmful content")

    def _prepare_conversation_context(
        self, user, conversation_id: str, conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Prepare conversation context with strict enforcement of the 6 message limit
        and create a summary of older messages when needed
        """
        if not conversation_history:
            return {"recent_messages": [], "has_summary": False}

        # Always strictly limit to the 6 most recent messages
        recent_messages = (
            conversation_history[-self.history_limit :]
            if len(conversation_history) > self.history_limit
            else conversation_history
        )

        # Check if we need a summary (if there are older messages)
        needs_summary = len(conversation_history) > self.history_limit

        if needs_summary:
            # Get or create a conversation summary for the older messages
            try:
                # Get older messages that need summarization
                older_messages = conversation_history[: -self.history_limit]

                # Get existing summary or create a new one
                summary = conversation_summary_service.get_or_create_summary(
                    conversation_id, user, older_messages
                )

                return {
                    "recent_messages": recent_messages,
                    "has_summary": True,
                    "summary": summary.get("text", "Previous conversation"),
                    "key_points": summary.get("key_points", []),
                    "emotional_context": summary.get("emotional_context", {}),
                }
            except Exception as e:
                logger.error(f"Error getting conversation summary: {str(e)}")

        # Return just the recent messages if no summary needed or if summary creation failed
        return {"recent_messages": recent_messages, "has_summary": False}

    def _check_and_update_conversation_summary(
        self, user, conversation_id: str, conversation_history: list = None
    ) -> None:
        """Check if summary needs updating and schedule the update"""
        if not conversation_history or len(conversation_history) <= self.history_limit:
            return

        # Only update summary if we have a significant number of new messages since last summary
        try:
            # This would ideally be a background task
            conversation_summary_service.update_conversation_summary(
                conversation_id, user, conversation_history
            )
            logger.info(
                f"Updated conversation summary for conversation {conversation_id}"
            )
        except Exception as e:
            logger.error(f"Error updating conversation summary: {str(e)}")

    def _get_user_data(self, user) -> Dict[str, Any]:
        """Retrieve user's journal entries and mood logs"""
        try:
            # Define the lookback period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=self.lookback_days)

            # Get recent journal entries
            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("-created_at")[: self.journal_limit]

            # Get recent mood logs
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("-logged_at")[: self.mood_limit]

            # Format the data
            journal_data = []
            for entry in journal_entries:
                journal_data.append(
                    {
                        "date": entry.created_at.strftime("%Y-%m-%d"),
                        "content": entry.content,
                        "mood": entry.mood if hasattr(entry, "mood") else None,
                        "activities": entry.activities
                        if hasattr(entry, "activities")
                        else None,
                    }
                )

            mood_data = []
            for log in mood_logs:
                mood_data.append(
                    {
                        "date": log.logged_at.strftime("%Y-%m-%d"),
                        "mood_rating": log.mood_rating,
                        "activities": log.activities
                        if hasattr(log, "activities")
                        else None,
                        "notes": log.notes if hasattr(log, "notes") else None,
                    }
                )

            # Get enhanced AI analysis
            analysis = self._get_enhanced_ai_analysis(user)

            return {
                "journal_entries": journal_data,
                "mood_logs": mood_data,
                "analysis": analysis,
            }

        except Exception as e:
            logger.error(f"Error retrieving user data: {str(e)}")
            return {"error": str(e)}

    def _get_enhanced_ai_analysis(self, user) -> Dict[str, Any]:
        """Get enhanced AI analysis including social interaction and communication patterns"""
        try:
            from AI_engine.models import (
                UserAnalysis,
                SocialInteractionAnalysis,
                CommunicationPatternAnalysis,
                MedicationEffectAnalysis,
            )

            analysis = {}

            # Get basic user analysis
            latest_analysis = (
                UserAnalysis.objects.filter(user=user)
                .order_by("-analysis_date")
                .first()
            )
            if latest_analysis:
                analysis.update(
                    {
                        "mood_score": latest_analysis.mood_score,
                        "sentiment_score": latest_analysis.sentiment_score,
                        "dominant_emotions": latest_analysis.dominant_emotions,
                        "topics_of_concern": latest_analysis.topics_of_concern,
                        "suggested_activities": latest_analysis.suggested_activities,
                    }
                )

            # Get social interaction analysis
            social_analysis = (
                SocialInteractionAnalysis.objects.filter(user=user)
                .order_by("-analysis_date")
                .first()
            )
            if social_analysis:
                analysis["social_patterns"] = {
                    "engagement_score": social_analysis.engagement_score,
                    "therapeutic_content": social_analysis.therapeutic_content[
                        :3
                    ],  # Limit to top 3
                    "support_network": social_analysis.support_network,
                }

            # Get communication pattern analysis
            comm_analysis = (
                CommunicationPatternAnalysis.objects.filter(user=user)
                .order_by("-analysis_date")
                .first()
            )
            if comm_analysis:
                analysis["communication_patterns"] = {
                    "communication_style": comm_analysis.communication_style,
                    "response_patterns": comm_analysis.response_patterns,
                    "emotional_triggers": comm_analysis.emotional_triggers[
                        :3
                    ],  # Limit to top 3
                }

            # Get medication effect analysis
            med_analysis = (
                MedicationEffectAnalysis.objects.filter(user=user)
                .order_by("-analysis_date")
                .first()
            )
            if med_analysis:
                analysis["medication_effects"] = {
                    "medications": med_analysis.medications[:3],  # Limit to top 3
                    "mood_effects": med_analysis.mood_effects,
                    "side_effects": med_analysis.side_effects_detected[
                        :3
                    ],  # Limit to top 3
                }

            return analysis

        except Exception as e:
            logger.warning(f"Could not retrieve enhanced AI analysis: {str(e)}")
            return None

    def _build_prompt(
        self,
        message: str,
        conversation_context: Dict = None,
        user_data: Dict = None,
        user=None,
    ) -> str:
        """Build an improved and optimized prompt with better context integration"""
        user_name = user.get_full_name() or user.username if user else "User"

        prompt = f"""You are MindCare AI, a therapeutic mental health assistant having a conversation with {user_name}. 
Respond in a compassionate, helpful manner focusing on mental health support and therapeutic approaches.

CONVERSATION GOAL: Provide personalized mental health support using the user's data, history, and the current conversation context.

"""

        # Add conversation summary first if available
        if conversation_context and conversation_context.get("has_summary"):
            prompt += f"""CONVERSATION SUMMARY:
{conversation_context.get('summary', 'The conversation covered various mental health topics.')}

Key points from earlier conversation:
"""
            for point in conversation_context.get(
                "key_points", ["General discussion about mental health"]
            )[:3]:  # Limit to top 3 points
                prompt += f"- {point}\n"

            # Add emotional context if available
            if conversation_context.get("emotional_context"):
                emotional_context = conversation_context.get("emotional_context", {})
                prompt += f"\nEmotional tone: {emotional_context.get('overall_tone', 'neutral')}"

                # Add emotional progression if available
                if emotional_context.get("progression"):
                    prompt += f"\nEmotional progression: {emotional_context.get('progression')}"

            prompt += "\n"

        # Add enhanced user analysis data
        if user_data and not user_data.get("error"):
            prompt += "\nUSER DATA INSIGHTS:\n"

            # Add analysis data if available
            if user_data.get("analysis"):
                analysis = user_data["analysis"]

                # Create a personalized context section based on analysis
                if "mood_score" in analysis or "dominant_emotions" in analysis:
                    prompt += "Emotional State: "
                    if "mood_score" in analysis:
                        mood_label = (
                            "positive"
                            if analysis.get("mood_score", 5) > 5
                            else "neutral"
                            if analysis.get("mood_score", 5) == 5
                            else "negative"
                        )
                        prompt += f"{mood_label} (score: {analysis.get('mood_score', 5)}/10), "

                    if (
                        "dominant_emotions" in analysis
                        and analysis["dominant_emotions"]
                    ):
                        prompt += f"primarily experiencing {', '.join(analysis['dominant_emotions'][:2])}\n"
                    else:
                        prompt += "\n"

                # Add concerns and topics
                if "topics_of_concern" in analysis and analysis["topics_of_concern"]:
                    prompt += f"Primary concerns: {', '.join(analysis['topics_of_concern'][:3])}\n"

                # Add social context if available
                if analysis.get("social_patterns"):
                    social = analysis["social_patterns"]
                    prompt += f"Social context: {social.get('engagement_score', 'moderate')}/10 engagement, "
                    prompt += f"{social.get('support_network', {}).get('strength', 'moderate')} support network\n"

                # Add communication patterns if available
                if analysis.get("communication_patterns"):
                    comm = analysis["communication_patterns"]
                    if comm.get("communication_style"):
                        prompt += (
                            f"Communication style: {comm.get('communication_style')}\n"
                        )

                    # Add emotional triggers for careful navigation
                    if comm.get("emotional_triggers"):
                        prompt += f"Approach carefully: {', '.join(comm['emotional_triggers'][:2])}\n"

                # Add medication context if relevant
                if analysis.get("medication_effects", {}).get("medications"):
                    meds = analysis["medication_effects"]
                    prompt += (
                        f"Medication context: On {', '.join(meds['medications'][:2])}"
                    )
                    if meds.get("mood_effects"):
                        prompt += f" with {meds['mood_effects'].get('impact', 'unknown')} impact on mood"
                    prompt += "\n"

                # Add suggested activities
                if analysis.get("suggested_activities"):
                    prompt += f"Recommended activities: {', '.join(analysis['suggested_activities'][:3])}\n"

            # Add recent mood data (condensed)
            if user_data.get("mood_logs") and len(user_data["mood_logs"]) > 0:
                prompt += "\nMOOD TRENDS: "
                # Extract last 3 mood ratings to show trend
                recent_moods = user_data["mood_logs"][:3]
                mood_values = [log.get("mood_rating", 5) for log in recent_moods]
                mood_dates = [log.get("date", "recent") for log in recent_moods]

                if len(mood_values) >= 2:
                    # Show trend
                    trend = (
                        "improving"
                        if mood_values[0] > mood_values[-1]
                        else "stable"
                        if mood_values[0] == mood_values[-1]
                        else "declining"
                    )
                    prompt += f"{trend}, most recent rating {mood_values[0]}/10 on {mood_dates[0]}\n"
                elif len(mood_values) == 1:
                    prompt += (
                        f"most recent rating {mood_values[0]}/10 on {mood_dates[0]}\n"
                    )

            # Add recent journal insight (very condensed)
            if (
                user_data.get("journal_entries")
                and len(user_data["journal_entries"]) > 0
            ):
                recent_entry = user_data["journal_entries"][0]
                # Extract a brief snippet
                content = recent_entry.get("content", "")
                snippet = content[:100] + "..." if len(content) > 100 else content
                prompt += f"\nRECENT JOURNAL ({recent_entry.get('date', 'recent')}): {snippet}\n"

        # Add recent conversation - strictly limit to the 6 most recent messages
        prompt += "\nRECENT CONVERSATION:\n"
        if conversation_context and conversation_context.get("recent_messages"):
            for msg in conversation_context["recent_messages"][
                -self.history_limit :
            ]:  # Ensure strict limit
                role = "Assistant" if msg.get("is_bot", False) else "User"
                content = msg.get("content", "")
                # Truncate very long messages
                if len(content) > 200:
                    content = content[:197] + "..."
                prompt += f"{role}: {content}\n"

        # Add current message
        prompt += f"\nUser: {message}\n\nAssistant:"

        # Add detailed instruction footer
        prompt += """

RESPONSE GUIDELINES:
1. Be empathetic and supportive while focusing on therapeutic value
2. Personalize using the user's specific data, history, and conversation context
3. Reference insights from their mood trends, journal entries, or past conversations when relevant
4. Maintain a warm, conversational tone while providing evidence-based guidance
5. Suggest specific actionable techniques relevant to their situation
6. Be concise but thorough in your response
7. Address any topics of concern identified in their analysis when appropriate
8. If they reveal new information, acknowledge how it connects to their overall mental health picture
"""

        return prompt

    def _error_response(self, message: str) -> Dict[str, any]:
        """Generate error response"""
        return {
            "content": "I apologize, but I'm having trouble processing your message right now. Please try again in a moment.",
            "metadata": {"error": message},
        }


# Create singleton instance
chatbot_service = ChatbotService()

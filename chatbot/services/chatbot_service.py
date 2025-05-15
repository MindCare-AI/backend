# chatbot/services/chatbot_service.py
from typing import Dict, Any
import logging
from django.conf import settings
import re
import requests
from django.utils import timezone
from datetime import timedelta
from AI_engine.services.conversation_summary import conversation_summary_service
from journal.models import JournalEntry, JournalCategory
from mood.models import MoodLog
from ..exceptions import ChatbotAPIError
from .rag.therapy_rag_service import therapy_rag_service

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

    # Define reusable prompt templates as class constants
    SYSTEM_TEMPLATE = """\
SYSTEM: You are MindCare AI, a compassionate mental health assistant. 
Follow these rules strictly:
- Always begin by naming the recommended therapy approach.
- Use at least two core principles by name.
- Incorporate at least one concrete, step-by-step technique.
- Conclude with an encouraging, empathetic closing statement.
- Tone: empathetic, non-judgmental, clear.
- Format your response in 4 sections exactly:
    1. Overview of [Therapy Name]
    2. Key Principles: • principle A • principle B
    3. Technique Steps: 1. … 2. …
    4. Closing Statement
"""

    FEW_SHOT_EXAMPLES = """\
### Example 1
USER: “I have racing thoughts and can’t focus on work.”
ASSISTANT:
1. Overview of CBT  
   CBT (Cognitive Behavioral Therapy) focuses on identifying and challenging cognitive distortions.  
2. Key Principles: • Cognitive Distortions • Behavioral Activation  
3. Technique Steps:  
   1. Keep a thought record when you notice racing thoughts.  
   2. Schedule a 5-minute focused “work sprint” followed by a reward break.  
4. Closing Statement  
   You’re making progress by noticing patterns—keep practicing these steps!

### Example 2
USER: “I feel overwhelmed by intense emotions and don’t know what to do.”
ASSISTANT:
1. Overview of DBT  
   DBT (Dialectical Behavior Therapy) combines acceptance and change strategies to regulate emotions.  
2. Key Principles: • Distress Tolerance • Emotion Regulation  
3. Technique Steps:  
   1. Use TIPP: Temperature, Intense exercise, Paced breathing, Progressive relaxation.  
   2. Practice “wise mind” mindfulness for 2 minutes when emotions surge.  
4. Closing Statement  
   You’re not alone—these skills can help you regain balance.
"""

    def __init__(self):
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
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
        """Get response from Gemini with integrated RAG therapy recommendation"""
        try:
            safety_check = self._check_content_safety(message)
            if safety_check["is_harmful"]:
                return self._handle_harmful_content(
                    user, message, safety_check["category"]
                )

            user_data = self._get_user_data(user)
            conversation_context = self._prepare_conversation_context(
                user, conversation_id, conversation_history
            )
            # Get therapy recommendation via RAG service
            therapy_recommendation = self._get_therapy_recommendation(
                message, user_data
            )
            prompt = self._build_prompt(
                message, conversation_context, user_data, user, therapy_recommendation
            )

            response = self._call_gemini_api(prompt)
            self._check_and_update_conversation_summary(
                user, conversation_id, conversation_history
            )
            return {
                "content": response["text"],
                "metadata": {
                    **response.get("metadata", {}),
                    "therapy_recommendation": {
                        "approach": therapy_recommendation.get(
                            "recommended_approach", "unknown"
                        ),
                        "confidence": therapy_recommendation.get("confidence", 0.0),
                    },
                },
            }
        except Exception as e:
            logger.error(f"Error getting chatbot response: {str(e)}")
            return self._error_response(str(e))

    def _get_therapy_recommendation(
        self, message: str, user_data: Dict = None
    ) -> Dict[str, Any]:
        """Get therapy approach recommendation using RAG service.
        This method now fully relies on the RAG service.
        """
        try:
            recommendation = therapy_rag_service.get_therapy_approach(
                message, user_data
            )
            logger.info(f"Therapy recommendation: {recommendation}")
            return recommendation
        except Exception as e:
            logger.warning(
                f"Error getting therapy recommendation from RAG service: {str(e)}"
            )
            return {
                "recommended_approach": "unknown",
                "confidence": 0.0,
                "therapy_info": {
                    "name": "General Therapeutic Approach",
                    "description": "A personalized therapeutic approach combining various methods.",
                    "core_principles": [],
                },
                "recommended_techniques": [],
                "alternative_approach": "unknown",
            }

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

        # Create specialized prompt for handling harmful content
        prompt = f"""You are MindCare AI, a therapeutic chatbot assistant. The user has expressed potentially harmful content 
related to {category}. Your response must:

1. Remain calm, professional and compassionate
2. Acknowledge their feelings without agreeing with harmful views
3. Gently redirect the conversation toward exploring underlying emotions
4. Offer support and perspective
5. Avoid judgment while maintaining clear ethical boundaries
6. Do not repeat or quote the exact harmful statement back to them
7. Provide a therapeutic perspective that shows empathy while discouraging harmful attitudes

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
            conversation_summary_service.update_summary(
                conversation_id, user, conversation_history
            )
            logger.info(
                f"Updated conversation summary for conversation {conversation_id}"
            )
        except Exception as e:
            logger.error(f"Error updating conversation summary: {str(e)}")

    def _get_user_data(self, user) -> Dict[str, Any]:
        """Retrieve user's journal entries, categories and mood logs"""
        try:
            # Define the lookback period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=self.lookback_days)

            # Get recent journal entries
            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("-created_at")[: self.journal_limit]

            # Get journal categories with entries
            journal_categories = JournalCategory.objects.filter(
                user=user, entries__created_at__range=(start_date, end_date)
            ).distinct()

            # Format journal entries
            journal_data = []
            for entry in journal_entries:
                journal_data.append(
                    {
                        "date": entry.created_at.strftime("%Y-%m-%d"),
                        "title": entry.title or f"Entry {entry.id}",
                        "content": entry.content,
                        "mood": entry.mood if hasattr(entry, "mood") else None,
                        "activities": entry.activities
                        if hasattr(entry, "activities")
                        else None,
                        "category": entry.category.name
                        if entry.category
                        else "Uncategorized",
                    }
                )

            # Format categories data
            categories_data = []
            for category in journal_categories:
                recent_entries = category.entries.filter(
                    created_at__range=(start_date, end_date)
                ).order_by("-created_at")[:3]

                entries_data = []
                for entry in recent_entries:
                    entries_data.append(
                        {
                            "date": entry.created_at.strftime("%Y-%m-%d"),
                            "content": entry.content[:100] + "..."
                            if len(entry.content) > 100
                            else entry.content,
                            "mood": entry.mood if hasattr(entry, "mood") else None,
                        }
                    )

                categories_data.append(
                    {
                        "name": category.name,
                        "entries_count": recent_entries.count(),
                        "recent_entries": entries_data,
                    }
                )

            # Get recent mood logs
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("-logged_at")[: self.mood_limit]

            # Format the mood data
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
                "journal_categories": categories_data,
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
        therapy_recommendation: Dict = None,
    ) -> str:
        """Build an improved prompt integrating the RAG therapy recommendation."""
        user_name = user.get_full_name() or user.username if user else "User"

        # Detect potential crisis keywords in the message
        is_crisis = self._detect_crisis_indicators(message)
        
        # Assemble the base prompt
        prompt = "\n".join([
            self.SYSTEM_TEMPLATE,
            self.FEW_SHOT_EXAMPLES,
            f"USER: \"{message}\"",
            "ASSISTANT:"
        ])

        # Build the enhanced context to inject before ASSISTANT:
        enhanced_context = []
        
        # 1. User History Context Integration
        if user_data:
            # Add journal entries summary if available
            if user_data.get("journal_entries"):
                recent_entries = user_data["journal_entries"][:3]
                topics = ", ".join([entry.get("title", "Entry") for entry in recent_entries])
                enhanced_context.append(f"SYSTEM: User has recently journaled about: {topics}")
            
            # Add mood patterns if available
            if user_data.get("mood_logs"):
                mood_ratings = [log.get("mood_rating", 0) for log in user_data.get("mood_logs", [])]
                if mood_ratings:
                    avg_mood = sum(mood_ratings) / len(mood_ratings)
                    mood_trend = "declining" if len(mood_ratings) > 1 and mood_ratings[0] < mood_ratings[-1] else "improving" if len(mood_ratings) > 1 and mood_ratings[0] > mood_ratings[-1] else "stable"
                    enhanced_context.append(f"SYSTEM: User's recent mood trend: {mood_trend} (avg: {avg_mood:.1f}/10)")

        # 2. Emotional Context Awareness
        if user_data and user_data.get("analysis"):
            analysis = user_data["analysis"]
            
            # Add emotional patterns
            if analysis.get("dominant_emotions"):
                emotions = ", ".join(analysis.get("dominant_emotions", [])[:3])
                enhanced_context.append(f"SYSTEM: Dominant emotions: {emotions}")
            
            # Add sentiment data
            if analysis.get("sentiment_score") is not None:
                sentiment = analysis.get("sentiment_score")
                enhanced_context.append(f"SYSTEM: Overall sentiment: {sentiment:.2f} (-1 to 1 scale)")

        # 3. Therapy-Specific Techniques
        if therapy_recommendation and therapy_recommendation.get("recommended_approach") != "unknown":
            name = therapy_recommendation["therapy_info"]["name"]
            confidence = int(therapy_recommendation["confidence"] * 100)
            principles = therapy_recommendation["therapy_info"]["core_principles"][:2]
            
            # Get more detailed techniques
            all_techniques = therapy_recommendation.get("recommended_techniques", [])
            techniques = [t for t in all_techniques[:3] if "name" in t]
            technique_names = [t["name"] for t in techniques]
            
            # Add therapy recommendations
            enhanced_context.append(f"SYSTEM: Recommended Approach: {name} ({confidence}% confidence)")
            enhanced_context.append(f"SYSTEM: Core Principles: {principles[0]}, {principles[1]}")
            enhanced_context.append(f"SYSTEM: Techniques to Include: {', '.join(technique_names)}")
            
            # Add specific exercises if available
            if all_techniques and len(all_techniques) > 0 and "steps" in all_techniques[0]:
                enhanced_context.append(f"SYSTEM: Exercise: {all_techniques[0]['name']} - {'; '.join(all_techniques[0].get('steps', [])[:3])}")

        # 4. Personalization Enhancements
        enhanced_context.append(f"SYSTEM: User Name: {user_name}")
        
        # Add past successful techniques if available
        if user_data and user_data.get("analysis") and user_data["analysis"].get("suggested_activities"):
            activities = user_data["analysis"].get("suggested_activities", [])[:2]
            if activities:
                enhanced_context.append(f"SYSTEM: Previously helpful activities: {', '.join(activities)}")

        # 5. Conversation Continuity
        if conversation_context:
            if conversation_context.get("has_summary") and conversation_context.get("summary"):
                enhanced_context.append(f"SYSTEM: Past conversation summary: {conversation_context['summary']}")
            
            if conversation_context.get("key_points"):
                key_points = ", ".join(conversation_context.get("key_points", [])[:3])
                enhanced_context.append(f"SYSTEM: Key topics discussed: {key_points}")

        # 6. Enhanced Safety and Crisis Detection
        if is_crisis:
            enhanced_context.append("SYSTEM: PRIORITY ALERT - Potential crisis detected. Provide immediate support resources and crisis intervention.")

        # 7. Cultural Sensitivity
        if user and hasattr(user, "profile") and hasattr(user.profile, "cultural_background"):
            enhanced_context.append(f"SYSTEM: Consider cultural context: {user.profile.cultural_background}")
        else:
            enhanced_context.append("SYSTEM: Maintain cultural sensitivity and avoid assumptions about background or beliefs.")

        # 8. Goal-Oriented Framing
        if user_data and user_data.get("analysis") and user_data["analysis"].get("topics_of_concern"):
            topics = user_data["analysis"].get("topics_of_concern", [])[:2]
            if topics:
                enhanced_context.append(f"SYSTEM: User's therapeutic focus areas: {', '.join(topics)}")

        # Insert the enhanced context before ASSISTANT:
        if enhanced_context:
            prompt = prompt.replace(
                "ASSISTANT:",
                "\n".join(enhanced_context) + "\n\nASSISTANT:"
            )

        return prompt

    def _detect_crisis_indicators(self, message: str) -> bool:
        """Detect potential crisis indicators in a message."""
        crisis_keywords = [
            r'suicid(e|al)', r'kill (myself|me)', r'want to die', r'end (my|this) life',
            r'harm(ing)? myself', r'no reason to live', r'better off dead', r'emergency',
            r'crisis', r'urgent help', r'immediate danger', r'overdose', r'self-harm'
        ]
        
        message_lower = message.lower()
        for keyword in crisis_keywords:
            if re.search(keyword, message_lower):
                return True
                
        return False

    def _error_response(self, message: str) -> Dict[str, any]:
        """Generate error response"""
        return {
            "content": "I apologize, but I'm having trouble processing your message right now. Please try again in a moment.",
            "metadata": {"error": message},
        }


# Create singleton instance
chatbot_service = ChatbotService()

# chatbot/services/chatbot_service.py
from typing import Dict, Any
import logging
import re
import random  # Add missing import for randomization in humanize_response
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from AI_engine.services.conversation_summary import conversation_summary_service
from journal.models import JournalEntry, JournalCategory
from mood.models import MoodLog
from ..exceptions import ChatbotAPIError
from .rag.therapy_rag_service import therapy_rag_service
from AI_engine.services.crisis_monitoring import crisis_monitoring_service

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
SYSTEM: You are a compassionate mental health professional. 
Respond in a warm, conversational style with these guidelines:
- Begin with empathetic acknowledgment of the person's situation
- Use natural, everyday language a therapist would use
- Avoid sounding like an AI or using technical language
- Share therapeutic insights in a personal, caring way
- Never mention "AI," "analysis," "algorithms," or "processing"
- Speak as if you're in a face-to-face conversation
- Use contractions, varied sentence lengths, and occasional thoughtful pauses
- Maintain a gentle, supportive tone throughout
"""

    FEW_SHOT_EXAMPLES = """\
### Example 1
USER: "I have racing thoughts and can't focus on work."
ASSISTANT:
I can see how that would be really frustrating. Those racing thoughts can make it nearly impossible to concentrate on anything, can't they? 

What's often helpful in these situations is taking a step back to notice these thought patterns. Maybe try keeping a quick note of when they happen? Many people find that just becoming aware of these patterns helps slow them down.

You might also try a simple technique - setting a timer for just 5 minutes of focused work, followed by a small reward. It's surprising how breaking things down into tiny steps can help.

Remember, this is something many people struggle with. You're not alone in this, and noticing the pattern is already a significant first step.

### Example 2
USER: "I feel overwhelmed by intense emotions and don't know what to do."
ASSISTANT:
That feeling of being overwhelmed can be so difficult to handle. When emotions feel that intense, it's like they're taking over everything, isn't it?

I've seen many people find relief through some simple physical strategies when emotions surge. Something as straightforward as changing your body temperature - maybe splashing cold water on your face or doing brief, intense exercise - can help create some immediate distance from those overwhelming feelings.

It might also help to practice taking a moment to just observe what's happening in your body when emotions rise. Just noticing "this is what I'm feeling right now" without judgment.

These intense emotional waves do pass, even when it doesn't feel like they will. You're showing real courage by reaching out - that's actually a powerful way of taking care of yourself.
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
        self.crisis_settings = getattr(settings, "CRISIS_RESPONSE_SETTINGS", {})
        self.high_priority_keywords = self.crisis_settings.get("HIGH_PRIORITY_KEYWORDS", [])
        self.min_crisis_confidence = self.crisis_settings.get("MIN_CRISIS_CONFIDENCE", 0.6)

    def get_response(self, user, message, conversation_id, conversation_history):
        # Store user name for humanization
        self._current_user_name = user.get_full_name() or user.username
        
        # 1) Crisis override
        crisis_detection = self._enhanced_crisis_detection(message)
        if crisis_detection["is_crisis"] and crisis_detection["confidence"] >= self.min_crisis_confidence:
            logger.critical(
                f"CRISIS CONTENT DETECTED: User {user.id} - '{message}' "
                f"(conf={crisis_detection['confidence']:.2f}, cat={crisis_detection['category']})"
            )
            # log to DB for audit/follow-up
            crisis_monitoring_service.log_crisis_event(user, message, crisis_detection)
            # generate and tag response
            crisis_response = self._generate_crisis_response(user, message, crisis_detection)
            crisis_response["metadata"]["chatbot_method"] = "crisis_protocol"
            crisis_response["chatbot_method"] = "crisis_protocol"
            return crisis_response

        # If not a crisis, proceed with normal response flow
        # 1. Get RAG recommendation
        context = conversation_summary_service.get_conversation_context(
            conversation_id, user
        )

        rec = therapy_rag_service.get_therapy_approach(
            query=message,
            user_data={
                "recent_messages": context.get("recent_messages"),
                "analysis": context.get("summary"),
            },
        )
        method = rec.get("recommended_approach", "unknown")
        conf = rec.get("confidence", 0.0)

        # 2. Use GEMINI + RAG for actual response generation
        try:
            # Build enhanced prompt with RAG context
            user_data = self._get_user_data(user)
            conversation_context = self._prepare_conversation_context(
                user, conversation_id, conversation_history
            )

            prompt = self._build_prompt(
                message=message,
                conversation_context=conversation_context,
                user_data=user_data,
                user=user,
                therapy_recommendation=rec,
            )

            # Generate response using Gemini API
            gemini_response = self._call_gemini_api(prompt)

            content = gemini_response.get(
                "text", "I'm having trouble generating a response."
            )

            metadata = {
                "chatbot_method": method,
                "therapy_recommendation": rec,
                "ai_system": "Gemini + Local RAG",
                "model": "gemini-2.0-flash",
                "vector_store": "local_file_based",
                "rag_confidence": conf,
            }

            response_data = {"content": content, "metadata": metadata}
            # Process response to ensure consistent chatbot_method at both levels
            return self._process_bot_response(response_data, message)

        except Exception as e:
            logger.error(f"Error with Gemini API: {str(e)}")
            # Fallback to current simple response
            content = (
                f"I've analyzed your message using our local AI system.\n\n"
                f"• Context summary: {context.get('summary','No summary available')}\n\n"
                f"Based on my RAG analysis, I recommend *{method.upper()}* therapy (confidence: {conf:.2f}).\n"
                f"Key evidence: {rec.get('supporting_evidence',[])[:3]}\n"
                f"Suggested techniques: {[t.get('name') for t in rec.get('recommended_techniques',[])]}\n\n"
                f"This recommendation comes from analyzing {len(rec.get('supporting_chunks', []))} relevant therapy documents.\n"
                f"Feel free to ask more specific questions about {method.upper()} techniques!"
            )

            metadata = {
                "chatbot_method": method,
                "therapy_recommendation": rec,
                "ai_system": "Ollama + Local RAG (Fallback)",
                "model": "mistral",
                "vector_store": "local_file_based",
            }

            response_data = {"content": content, "metadata": metadata}
            # Process fallback response as well
            return self._process_bot_response(response_data, message)

    def get_response_with_gemini(
        self, user, message, conversation_id, conversation_history
    ):
        # 1. Get RAG recommendation first
        context = conversation_summary_service.get_conversation_context(
            conversation_id, user
        )

        rec = therapy_rag_service.get_therapy_approach(
            query=message,
            user_data={
                "recent_messages": context.get("recent_messages"),
                "analysis": context.get("summary"),
            },
        )

        # 2. Build enhanced prompt for Gemini
        therapy_context = f"""
Based on RAG analysis:
- Recommended therapy: {rec.get('recommended_approach', 'unknown')}
- Confidence: {rec.get('confidence', 0):.2f}
- Key techniques: {[t.get('name') for t in rec.get('recommended_techniques', [])]}
- Supporting evidence: {rec.get('supporting_evidence', [])}

User message: "{message}"

Provide a therapeutic response using the recommended approach.
"""

        # 3. Call Gemini API
        try:
            gemini_response = self._call_gemini_api(therapy_context)
            content = gemini_response.get(
                "text",
                "I apologize, but I'm having trouble generating a response right now.",
            )

            metadata = {
                "chatbot_method": rec.get("recommended_approach"),
                "therapy_recommendation": rec,
                "ai_system": "Gemini + Local RAG",
                "model": "gemini-2.0-flash",
                "rag_confidence": rec.get("confidence", 0),
            }

            response_data = {"content": content, "metadata": metadata}
            # Process response here too
            return self._process_bot_response(response_data, message)

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            # Fallback to current system
            return self.get_response(
                user, message, conversation_id, conversation_history
            )

    def _get_therapy_recommendation(
        self, message: str, user_data: Dict = None
    ) -> Dict[str, Any]:
        """Get therapy approach recommendation using RAG service."""
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
                r"\b(i('m)?\s*jew(s)?)\b",  # detect “i’m jews” or similar
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
                if re.search(pattern, message.lower()):
                    result.update({"is_harmful": True, "category": category, "confidence": 0.9})
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
        """Build an improved prompt integrating user data, therapy recommendations and conversation history."""
        # Get user's name for personalization
        user_name = user.get_full_name() or user.username if user else "User"

        # Detect potential crisis keywords in the message
        is_crisis = self._detect_crisis_indicators(message)

        # Assemble the base prompt with humanized instructions
        prompt = "\n".join(
            [
                self.SYSTEM_TEMPLATE,
                f"SYSTEM: The person's name is {user_name}. Respond warmly and personally to them.",
                "SYSTEM: Important guidelines for your response:",
                "- Never mention being an AI, a model, or a chatbot",
                "- Don't use phrases like 'I understand' or 'I'm here to help' repeatedly",
                "- Avoid clinical, technical language unless the person uses it first",
                "- Respond as if you're having a genuine conversation",
                "- If the person seems in crisis, respond with immediate care and resources",
                "- Don't label or structure your response with numbered sections",
                self.FEW_SHOT_EXAMPLES,
                f'USER: "{message}"',
                "ASSISTANT:",
            ]
        )

        # Build the enhanced context to inject before ASSISTANT:
        enhanced_context = []

        # 1. User History Context Integration - Journals and Mood
        if user_data:
            # Add journal entries with content summaries if available
            if user_data.get("journal_entries"):
                recent_entries = user_data["journal_entries"][:3]
                # Extract real content and details from journal entries
                journal_details = []
                for entry in recent_entries:
                    content_snippet = (
                        entry.get("content", "")[:100] + "..."
                        if entry.get("content") and len(entry.get("content", "")) > 100
                        else entry.get("content", "")
                    )
                    entry_date = entry.get("date", "recent")
                    mood = entry.get("mood", "unspecified")
                    category = entry.get("category", "general")
                    journal_details.append(
                        f'[{entry_date}, mood: {mood}, category: {category}]: "{content_snippet}"'
                    )

                if journal_details:
                    enhanced_context.append("SYSTEM: User's recent journal entries:")
                    for detail in journal_details:
                        enhanced_context.append(f"- {detail}")

            # Add detailed mood patterns if available
            if user_data.get("mood_logs"):
                mood_logs = user_data["mood_logs"]
                if mood_logs:
                    # Calculate patterns and trends
                    mood_ratings = [log.get("mood_rating", 0) for log in mood_logs]
                    activities = []
                    for log in mood_logs[:3]:
                        if log.get("activities"):
                            activities.extend(log.get("activities", []))

                    # Get unique activities
                    unique_activities = list(set(activities))[:5]
                    avg_mood = (
                        sum(mood_ratings) / len(mood_ratings) if mood_ratings else 0
                    )

                    # Determine trend
                    mood_trend = "stable"
                    if len(mood_ratings) > 1:
                        if mood_ratings[0] < mood_ratings[-1]:
                            mood_trend = "improving"
                        elif mood_ratings[0] > mood_ratings[-1]:
                            mood_trend = "declining"

                    enhanced_context.append(f"SYSTEM: {user_name}'s recent mood data:")
                    enhanced_context.append(
                        f"- Mood trend: {mood_trend} (average: {avg_mood:.1f}/10)"
                    )
                    if unique_activities:
                        enhanced_context.append(
                            f"- Recent activities: {', '.join(unique_activities)}"
                        )

        # 2. Emotional Context Awareness - AI Analysis of Emotions and Mental State
        if user_data and user_data.get("analysis"):
            analysis = user_data["analysis"]

            # Add emotional patterns with more context
            if analysis.get("dominant_emotions"):
                emotions = ", ".join(analysis.get("dominant_emotions", [])[:3])
                enhanced_context.append(
                    f"SYSTEM: {user_name}'s dominant emotions: {emotions}"
                )

            # Add sentiment data with interpretation
            if analysis.get("sentiment_score") is not None:
                sentiment = analysis.get("sentiment_score")
                sentiment_desc = (
                    "negative"
                    if sentiment < -0.3
                    else "neutral"
                    if -0.3 <= sentiment <= 0.3
                    else "positive"
                )
                enhanced_context.append(
                    f"SYSTEM: Overall sentiment analysis: {sentiment_desc} ({sentiment:.2f} on -1 to 1 scale)"
                )

            # Add medical analysis data
            if analysis.get("medication_effects"):
                med_effects = analysis.get("medication_effects")
                if med_effects.get("medications"):
                    meds = ", ".join(med_effects.get("medications", [])[:3])
                    enhanced_context.append(
                        f"SYSTEM: {user_name}'s medication context: {meds}"
                    )

                if med_effects.get("mood_effects"):
                    mood_impact = med_effects.get("mood_effects")
                    if isinstance(mood_impact, dict) and "description" in mood_impact:
                        enhanced_context.append(
                            f"SYSTEM: Medication impact: {mood_impact.get('description')}"
                        )
                    elif isinstance(mood_impact, str):
                        enhanced_context.append(
                            f"SYSTEM: Medication impact: {mood_impact}"
                        )

                if med_effects.get("side_effects_detected"):
                    side_effects = ", ".join(
                        med_effects.get("side_effects_detected", [])[:3]
                    )
                    if side_effects:
                        enhanced_context.append(
                            f"SYSTEM: Note potential side effects: {side_effects}"
                        )

        # Add social interaction analysis
        if (
            user_data
            and user_data.get("analysis")
            and user_data["analysis"].get("social_patterns")
        ):
            social = user_data["analysis"].get("social_patterns")

            if social.get("engagement_score") is not None:
                engagement = social.get("engagement_score")
                engagement_level = (
                    "low"
                    if engagement < 0.3
                    else "moderate"
                    if 0.3 <= engagement <= 0.7
                    else "high"
                )
                enhanced_context.append(
                    f"SYSTEM: {user_name}'s social engagement: {engagement_level}"
                )

            if social.get("support_network"):
                support = social.get("support_network")
                if isinstance(support, dict) and support.get("strength"):
                    enhanced_context.append(
                        f"SYSTEM: Support network strength: {support.get('strength')}"
                    )
                elif isinstance(support, str):
                    enhanced_context.append(f"SYSTEM: Support network: {support}")

            if (
                social.get("therapeutic_content")
                and len(social.get("therapeutic_content")) > 0
            ):
                helpful_content = (
                    social.get("therapeutic_content")[0]
                    if isinstance(social.get("therapeutic_content")[0], str)
                    else social.get("therapeutic_content")[0].get(
                        "description", "helpful interactions"
                    )
                )
                enhanced_context.append(
                    f"SYSTEM: Therapeutic content that helps {user_name}: {helpful_content}"
                )

        # 3. Therapy-Specific Techniques
        if (
            therapy_recommendation
            and therapy_recommendation.get("recommended_approach") != "unknown"
        ):
            name = therapy_recommendation["therapy_info"]["name"]
            confidence = int(therapy_recommendation["confidence"] * 100)
            principles = therapy_recommendation["therapy_info"]["core_principles"][:2]

            # Get more detailed techniques
            all_techniques = therapy_recommendation.get("recommended_techniques", [])
            techniques = [t for t in all_techniques[:3] if "name" in t]
            technique_names = [t["name"] for t in techniques]

            # Add therapy recommendations
            enhanced_context.append(
                f"SYSTEM: Recommended Approach: {name} ({confidence}% confidence)"
            )
            enhanced_context.append(
                f"SYSTEM: Core Principles: {principles[0]}, {principles[1]}"
            )
            enhanced_context.append(
                f"SYSTEM: Techniques to Include: {', '.join(technique_names)}"
            )

            # Add specific exercises if available
            if (
                all_techniques
                and len(all_techniques) > 0
                and "steps" in all_techniques[0]
            ):
                enhanced_context.append(
                    f"SYSTEM: Exercise: {all_techniques[0]['name']} - {'; '.join(all_techniques[0].get('steps', [])[:3])}"
                )

        # 4. Personalization Enhancements
        enhanced_context.append(f"SYSTEM: User Name: {user_name}")

        # Add past successful techniques if available
        if (
            user_data
            and user_data.get("analysis")
            and user_data["analysis"].get("suggested_activities")
        ):
            activities = user_data["analysis"].get("suggested_activities", [])[:2]
            if activities:
                enhanced_context.append(
                    f"SYSTEM: Previously helpful activities: {', '.join(activities)}"
                )

        # 5. Conversation Continuity - Enhanced with more context from conversation history
        if conversation_context:
            # Add conversation summary if available
            if conversation_context.get("has_summary") and conversation_context.get(
                "summary"
            ):
                enhanced_context.append(
                    f"SYSTEM: Past conversation summary: {conversation_context['summary']}"
                )

            # Add key points from conversation
            if conversation_context.get("key_points"):
                key_points = ", ".join(conversation_context.get("key_points", [])[:3])
                enhanced_context.append(
                    f"SYSTEM: Key topics discussed with {user_name}: {key_points}"
                )

            # Add emotional context from conversation history
            if conversation_context.get("emotional_context"):
                emotional_ctx = conversation_context.get("emotional_context", {})
                if emotional_ctx.get("overall_tone"):
                    enhanced_context.append(
                        f"SYSTEM: Previous conversation tone: {emotional_ctx.get('overall_tone')}"
                    )
                if isinstance(emotional_ctx, dict) and emotional_ctx.get(
                    "main_concerns"
                ):
                    concerns = ", ".join(emotional_ctx.get("main_concerns", [])[:2])
                    if concerns:
                        enhanced_context.append(
                            f"SYSTEM: {user_name}'s main concerns: {concerns}"
                        )

        # 6. Enhanced Safety and Crisis Detection
        if is_crisis:
            enhanced_context.append(
                f"SYSTEM: PRIORITY ALERT - Potential crisis detected for {user_name}. Provide immediate support resources and crisis intervention."
            )

        # 7. Cultural Sensitivity
        if (
            user
            and hasattr(user, "profile")
            and hasattr(user.profile, "cultural_background")
        ):
            enhanced_context.append(
                f"SYSTEM: Consider cultural context: {user.profile.cultural_background}"
            )
        else:
            enhanced_context.append(
                "SYSTEM: Maintain cultural sensitivity and avoid assumptions about background or beliefs."
            )

        # 8. Goal-Oriented Framing
        if (
            user_data
            and user_data.get("analysis")
            and user_data["analysis"].get("topics_of_concern")
        ):
            topics = user_data["analysis"].get("topics_of_concern", [])[:2]
            if topics:
                enhanced_context.append(
                    f"SYSTEM: {user_name}'s therapeutic focus areas: {', '.join(topics)}"
                )

        # 9. Communication Patterns Analysis
        if (
            user_data
            and user_data.get("analysis")
            and user_data["analysis"].get("communication_patterns")
        ):
            comm_patterns = user_data["analysis"].get("communication_patterns", {})

            if comm_patterns.get("communication_style"):
                style = comm_patterns.get("communication_style")
                if isinstance(style, dict) and style.get("primary_style"):
                    enhanced_context.append(
                        f"SYSTEM: {user_name}'s communication style: {style.get('primary_style')}"
                    )
                elif isinstance(style, str):
                    enhanced_context.append(
                        f"SYSTEM: {user_name}'s communication style: {style}"
                    )

            if (
                comm_patterns.get("emotional_triggers")
                and len(comm_patterns.get("emotional_triggers")) > 0
            ):
                triggers = ", ".join(comm_patterns.get("emotional_triggers", [])[:2])
                if triggers:
                    enhanced_context.append(
                        f"SYSTEM: Topics that may trigger emotional responses: {triggers}"
                    )

            if comm_patterns.get("response_patterns"):
                response_pattern = comm_patterns.get("response_patterns")
                if isinstance(response_pattern, dict) and response_pattern.get(
                    "best_approach"
                ):
                    enhanced_context.append(
                        f"SYSTEM: Best response approach: {response_pattern.get('best_approach')}"
                    )
                elif isinstance(response_pattern, str):
                    enhanced_context.append(
                        f"SYSTEM: Response pattern: {response_pattern}"
                    )

        # Insert the enhanced context before ASSISTANT:
        if enhanced_context:
            prompt = prompt.replace(
                "ASSISTANT:", "\n".join(enhanced_context) + "\n\nASSISTANT:"
            )

        return prompt

    def _humanize_response(self, content: str) -> str:
        """Make the response more human-like by removing robotic/AI-like language"""
        # Remove section numbers and headers
        content = re.sub(r'^\d+\.\s+(?:Overview|Key Principles|Technique Steps|Closing Statement)', '', content, flags=re.MULTILINE)
        
        # Remove bullet points at beginning of lines
        content = re.sub(r'^\s*•\s+', '', content, flags=re.MULTILINE)
        
        # Remove numbered lists at beginning of lines
        content = re.sub(r'^\s*\d+\.\s+', '', content, flags=re.MULTILINE)
        
        # Replace AI self-references
        ai_references = [
            r'As an AI', 
            r'I\'m an AI', 
            r'as a language model',
            r'As a mental health assistant',
            r'MindCare AI',
            r'I\'m a chatbot',
            r'I was designed to',
        ]
        
        for ref in ai_references:
            content = re.sub(ref, 'As a therapist', content, flags=re.IGNORECASE)
        
        # Replace clinical language with more conversational alternatives
        clinical_terms = {
            r'cognitive distortions': 'unhelpful thought patterns',
            r'behavioral activation': 'engaging in positive activities',
            r'dialectical behavior therapy': 'balanced approach to emotions',
            r'CBT techniques': 'thought-changing exercises',
            r'DBT skills': 'emotional balancing skills',
            r'mindfulness exercise': 'present-moment awareness practice',
            r'therapeutic intervention': 'helpful approach',
            r'emotional regulation': 'managing feelings',
            r'psychological assessment': 'understanding of your situation',
        }
        
        for term, replacement in clinical_terms.items():
            content = re.sub(term, replacement, content, flags=re.IGNORECASE)
        
        # Add some natural hesitations and fillers occasionally
        hesitations = [', you know?', ', if that makes sense', ' - well, ', ', I mean, ']
        if random.random() < 0.3:  # Only add occasionally
            random_position = random.randint(0, max(1, len(content) - 50))
            insert_position = content.find('. ', random_position)
            if insert_position > 0:
                random_hesitation = random.choice(hesitations)
                content = content[:insert_position] + random_hesitation + content[insert_position:]
        
        # Ensure the response feels personal by adding the user's name if not already present
        if hasattr(self, '_current_user_name') and self._current_user_name:
            if self._current_user_name not in content and len(content) > 100:
                sentences = content.split('. ')
                if len(sentences) > 2:
                    # Add name to the second or third sentence
                    insert_idx = random.randint(1, min(2, len(sentences)-1))
                    sentences[insert_idx] = f"{self._current_user_name}, {sentences[insert_idx][0].lower()}{sentences[insert_idx][1:]}"
                    content = '. '.join(sentences)
        
        return content

    def _enhanced_crisis_detection(self, message: str) -> Dict[str, Any]:
        """
        Enhanced detection of crisis content with confidence scoring
        """
        message_lower = message.lower()
        result = {
            "is_crisis": False,
            "confidence": 0.0,
            "category": None,
            "matched_terms": []
        }

        # Define more comprehensive crisis patterns with weights
        crisis_patterns = {
            "suicide": [
                (r"\bsuicid(e|al)\b", 0.9),
                (r"\bkill(ing)?\s+(my)?self\b", 0.95),
                (r"\bend\s+(my|this)\s+life\b", 0.9),
                (r"\bdon\'?t\s+want\s+to\s+(be\s+)?alive\b", 0.85),
                (r"\bwant\s+to\s+die\b", 0.9),
                (r"\bno\s+reason\s+to\s+live\b", 0.85),
                (r"\bstop\s+thinking\s+about\s+killing\s+myself\b", 0.95),
                (r"\bthoughts?\s+about\s+killing\s+myself\b", 0.9),
                (r"\bthinking\s+about\s+suicide\b", 0.9),
                # Add pattern for the specific message structure
                (r"\bsto\s+thining\s+killing\s+my\s+self\b", 0.95),  # Matches typos in user input
                (r"\bimprove\s+my\s+self\s+to\s+sto.*killing\b", 0.9),
            ],
            "self_harm": [
                (r"\bcut(ting)?\s+(my)?self\b", 0.8),
                (r"\bharm(ing)?\s+(my)?self\b", 0.8),
                (r"\bhurt(ing)?\s+(my)?self\b", 0.8),
                (r"\binjur(e|ing)\s+(my)?self\b", 0.8),
                (r"\bprevent\s+killing\s+(my)?self\b", 0.9),  # New pattern for help seeking
            ],
            "immediate_danger": [
                (r"\bhelp\s+me\s+now\b", 0.7),
                (r"\bemergency\b", 0.7),
                (r"\bcrisis\b", 0.7),
                (r"\bin\s+danger\b", 0.8),
                (r"\bplan\s+to\s+kill\b", 0.95),
                (r"\bhave\s+a\s+plan\b", 0.8),
            ]
        }

        # Check for exact matches of high priority keywords first
        high_priority_patterns = [
            "kill myself", "killing myself", "suicide", "want to die", 
            "end my life", "stop thinking about killing myself"
        ]
        
        for keyword in high_priority_patterns:
            if keyword in message_lower:
                result["is_crisis"] = True
                result["confidence"] = 0.99
                result["category"] = "high_priority_suicide"
                result["matched_terms"].append(keyword)
                return result

        # Check patterns with weighted confidence
        max_confidence = 0.0
        for category, patterns in crisis_patterns.items():
            for pattern, confidence in patterns:
                matches = re.findall(pattern, message_lower)
                if matches:
                    result["matched_terms"].append(pattern)
                    if confidence > max_confidence:
                        max_confidence = confidence
                        result["category"] = category

        # Determine if it's a crisis based on confidence threshold
        if max_confidence >= self.min_crisis_confidence:
            result["is_crisis"] = True
            result["confidence"] = max_confidence

        # Additional context-aware analysis for potential false positives
        if result["is_crisis"]:
            # Check for quotes or hypothetical discussions that might be false positives
            if re.search(r"\".*(" + "|".join(result["matched_terms"]) + ").*\"", message):
                result["confidence"] *= 0.7  # Reduce confidence for quoted text

            # Check for educational or third-person context
            educational_indicators = [
                r"\bwhat\s+to\s+do\s+if\b",
                r"\bhow\s+to\s+help\b",
                r"\bmy\s+friend\s+is\b"
            ]
            if any(re.search(pattern, message_lower) for pattern in educational_indicators):
                result["confidence"] *= 0.6  # Reduce confidence for educational context

        return result

    def _generate_crisis_response(self, user, message: str, crisis_detection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate specialized response for crisis situations with appropriate resources
        """
        user_name = user.get_full_name() or user.username
        
        # Enhanced crisis response that's more supportive and immediate
        response_template = f"""I'm deeply concerned about what you've shared, {user_name}. Having thoughts about ending your life is incredibly painful, and I want you to know that reaching out shows tremendous strength.

Right now, it's crucial to connect with someone who can provide immediate, specialized support:

**Immediate Help:**
• National Suicide Prevention Lifeline: 988 (available 24/7)
• Crisis Text Line: Text HOME to 741741
• If you're in immediate danger, please call 911 or go to your nearest emergency room

**You Are Not Alone:**
These thoughts, while overwhelming, are something that can be worked through with proper support. Many people who have felt exactly like you do now have found ways to manage these thoughts and build a life worth living.

The fact that you're asking how to improve and stop these thoughts tells me part of you wants to feel better - that's the part we need to nurture and strengthen.

Would you be willing to reach out to one of these resources right now? I'm here to support you, but these professionals are specifically trained to help with exactly what you're experiencing."""

        # Alert staff immediately for high-risk situations
        if crisis_detection["confidence"] > 0.8:
            self._alert_staff_about_crisis(user, message, crisis_detection)

        return {
            "content": response_template,
            "metadata": {
                "is_crisis_response": True,
                "crisis_category": crisis_detection["category"],
                "crisis_confidence": crisis_detection["confidence"],
                "crisis_matched_terms": crisis_detection["matched_terms"],
                "response_type": "emergency_intervention",
                "chatbot_method": "crisis_protocol",
                "priority": "critical"
            }
        }
        
    def _alert_staff_about_crisis(self, user, message: str, crisis_detection: Dict[str, Any]) -> None:
        """Alert appropriate staff members about the crisis situation"""
        try:
            # Import here to avoid circular imports
            from notifications.services import notification_service

            # Send high-priority notification to staff
            notification_service.send_notification(
                # Adjust recipient based on your staff/admin model
                recipient_group="mental_health_staff",
                notification_type="crisis_alert",
                title="URGENT: Crisis Content Detected",
                message=f"User {user.username} has shared potentially concerning content that needs immediate attention.",
                metadata={
                    "user_id": user.id,
                    "crisis_category": crisis_detection["category"],
                    "crisis_confidence": crisis_detection["confidence"],
                    "message_preview": message[:100] + "..." if len(message) > 100 else message,
                    "timestamp": timezone.now().isoformat()
                },
                priority="critical"
            )
            logger.info(f"Crisis alert sent for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send crisis alert: {str(e)}")

    # Replace the existing method with this enhanced version
    def _detect_crisis_indicators(self, message: str) -> bool:
        """Legacy method maintained for compatibility, now using enhanced detection"""
        crisis_detection = self._enhanced_crisis_detection(message)
        return crisis_detection["is_crisis"] and crisis_detection["confidence"] >= self.min_crisis_confidence

    def _determine_chatbot_method(self, metadata: Dict) -> str:
        """Determine the chatbot method based on metadata"""
        # First check if there's a crisis response
        if metadata.get("is_crisis_response"):
            return "crisis_protocol"
            
        # Then check if there's a therapy recommendation with sufficient confidence
        therapy_rec = metadata.get("therapy_recommendation", {})
        if therapy_rec and therapy_rec.get("recommended_approach"):
            approach = therapy_rec.get("recommended_approach")
            confidence = therapy_rec.get("confidence", 0)
            
            if approach and approach != "unknown" and confidence > 0.4:
                return approach
                
        # Then check the explicitly set method
        explicit_method = metadata.get("chatbot_method")
        if explicit_method and explicit_method not in ["unknown", "Not determined"]:
            return explicit_method
            
        # Default based on AI system used
        ai_system = metadata.get("ai_system", "")
        if "RAG" in ai_system:
            return "therapeutic_conversation"
            
        return "general_support"

    def _process_bot_response(self, response_data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Process the bot response data before returning to client"""
        # Ensure metadata exists
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        # Check if this is a crisis response and mark it clearly
        if response_data.get("metadata", {}).get("is_crisis_response"):
            response_data["metadata"]["chatbot_method"] = "crisis_protocol"
            response_data["chatbot_method"] = "crisis_protocol"
            return response_data

        # Determine and set the chatbot method consistently
        chatbot_method = self._determine_chatbot_method(response_data.get("metadata", {}))
        # Set it both in metadata and at root level for consistency
        response_data["metadata"]["chatbot_method"] = chatbot_method
        response_data["chatbot_method"] = chatbot_method

        # Post-process the response to make it more human-like
        if "content" in response_data:
            response_data["content"] = self._humanize_response(response_data["content"])
        return response_data

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "content": f"I'm sorry, but I'm having trouble processing your request at the moment. {message}",
            "metadata": {
                "error": True,
                "error_message": message,
                "chatbot_method": "error_response"
            }
        }

    async def get_chatbot_response(self, message: str, conversation_id: str = None, user=None) -> Dict[str, Any]:
        """Get response from chatbot for a given message"""
        try:
            # Store user name for personalization
            if user:
                self._current_user_name = user.get_full_name() or user.username
                
            # Check for crisis content
            crisis_detection = self._enhanced_crisis_detection(message)
            if crisis_detection["is_crisis"] and crisis_detection["confidence"] >= self.min_crisis_confidence:
                return self._generate_crisis_response(user, message, crisis_detection)
                
            # Get therapy approach using RAG
            try:
                rag_result = therapy_rag_service.get_therapy_approach(message)
                self._therapy_recommendation = rag_result
            except Exception as e:
                logger.error(f"Error getting therapy approach: {str(e)}")
                self._therapy_recommendation = None

            # Get user data and conversation context
            user_data = self._get_user_data(user)
            conversation_context = self._prepare_conversation_context(
                user, conversation_id, None
            )
            # Build prompt and generate response            
            prompt = self._build_prompt(
                message, conversation_context, user_data, user, self._therapy_recommendation
            )
            # Call Gemini API
            response = await self._call_gemini_api(prompt)
            
            # Add metadata
            if "metadata" not in response:
                response["metadata"] = {}
                
            # Add RAG information
            if self._therapy_recommendation:
                response["metadata"]["ai_system"] = "Gemini + Local RAG"
                response["metadata"]["vector_store"] = "local_file_based"
                response["metadata"]["rag_confidence"] = self._therapy_recommendation.get("confidence", 0)
                response["metadata"]["therapy_recommendation"] = self._therapy_recommendation.get("recommended_approach", "general_support")

            # Process response to make it more human-like and ensure chatbot_method is consistent
            return self._process_bot_response(response, message)
        except Exception as e:
            logger.error(f"Error in get_chatbot_response: {str(e)}")
            return self._error_response("Unable to get response from chatbot")

# Create singleton instance
chatbot_service = ChatbotService()

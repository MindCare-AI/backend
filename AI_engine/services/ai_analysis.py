# AI_engine/services/ai_analysis.py
from typing import Dict, Any, List
import logging
from django.conf import settings
import requests
from datetime import timedelta
from django.utils import timezone
from ..models import UserAnalysis, AIInsight
from mood.models import MoodLog
from journal.models import JournalEntry

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Service for handling AI analysis of therapy sessions and user data."""

    def __init__(self):
        self.api_key = getattr(settings, "AI_API_KEY", None)
        self.api_endpoint = getattr(settings, "AI_API_ENDPOINT", None)
        self.cache_timeout = getattr(
            settings, "AI_CACHE_TIMEOUT", 3600
        )  # 1 hour default
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.batch_size = settings.AI_ENGINE_SETTINGS["ANALYSIS_BATCH_SIZE"]
        self.max_period = settings.AI_ENGINE_SETTINGS["MAX_ANALYSIS_PERIOD"]
        self.min_data_points = settings.AI_ENGINE_SETTINGS["MIN_DATA_POINTS"]
        self.risk_threshold = settings.AI_ENGINE_SETTINGS["RISK_THRESHOLD"]

    def generate_text(self, prompt: str) -> Dict[str, Any]:
        """Generate text response using Ollama"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "text": result["response"],
                    "metadata": {
                        "model": self.model,
                        "finish_reason": result.get("done", True),
                    },
                }
            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                raise Exception(
                    f"Ollama request failed with status {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            raise Exception(f"Text generation failed: {str(e)}")

    def analyze_user_data(self, user, date_range=30) -> Dict[str, Any]:
        """Analyze user's data using Ollama for insights"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=date_range)

            # Get mood logs with correct field name
            mood_logs = self._get_mood_data(user, date_range)

            # Get journal entries
            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("-created_at")

            # Get health metrics
            health_metrics = self._get_health_metrics(user, date_range)

            if not mood_logs and not journal_entries:
                return self._create_default_analysis()

            # Prepare data for analysis
            data = {
                "mood_logs": mood_logs,
                "journal_entries": [
                    {
                        "content": entry.content,
                        "mood": entry.mood,
                        "activities": getattr(entry, "activities", []),
                        "timestamp": entry.created_at.isoformat(),
                    }
                    for entry in journal_entries
                ],
                "health_metrics": health_metrics,
            }

            # Get analysis from Ollama
            analysis = self._analyze_with_ollama(data)

            # Store analysis results with proper field mapping - removed health_metrics_correlation
            user_analysis = UserAnalysis.objects.create(
                user=user,
                mood_score=analysis.get("mood_score", 0),
                sentiment_score=analysis.get("sentiment_score", 0),
                dominant_emotions=analysis.get("emotions", []),
                topics_of_concern=analysis.get("topics", []),
                suggested_activities=analysis.get("activities", []),
                risk_factors=analysis.get("risks", {}),
                improvement_metrics=analysis.get("improvements", {}),
            )

            # Generate therapy recommendations based on analysis
            self._create_therapy_recommendations(user, analysis)

            # Run communication analysis if messaging data exists
            try:
                from .communication_analysis import communication_analysis_service

                comm_analysis = (
                    communication_analysis_service.analyze_communication_patterns(
                        user, days=date_range
                    )
                )
                analysis["communication_analysis_completed"] = True
            except Exception as e:
                logger.error(f"Communication analysis failed: {str(e)}")
                analysis["communication_analysis_completed"] = False

            # Generate insights if needed
            if analysis.get("needs_attention"):
                AIInsight.objects.create(
                    user=user,
                    insight_type="risk_alert",
                    insight_data={
                        "risk_factors": analysis["risks"],
                        "suggested_actions": analysis["activities"],
                    },
                    priority="high",
                )

            # Run medication analysis if patient profile exists
            try:
                from .medication_analysis import medication_analysis_service

                med_analysis = medication_analysis_service.analyze_medication_effects(
                    user, days=date_range
                )
                analysis["medication_analysis_completed"] = med_analysis.get(
                    "success", False
                )

                # More robust error handling - check for specific keys
                if med_analysis.get("success", False):
                    analysis["medication_effects"] = med_analysis.get(
                        "mood_effects", {}
                    )
                    analysis["medication_side_effects"] = med_analysis.get(
                        "side_effects_detected", []
                    )
                    analysis["medication_recommendations"] = med_analysis.get(
                        "recommendations", []
                    )

                    # Check for concerning medication effects
                    if med_analysis.get("needs_attention", False):
                        # Create dedicated medication insight
                        AIInsight.objects.create(
                            user=user,
                            insight_type="medication_alert",
                            insight_data={
                                "medications": med_analysis.get("medications", []),
                                "effects": med_analysis.get("mood_effects", {}),
                                "side_effects": med_analysis.get(
                                    "side_effects_detected", []
                                ),
                                "recommendations": med_analysis.get(
                                    "recommendations", []
                                ),
                            },
                            priority="high",
                        )
                else:
                    # Log specific failure reason
                    logger.info(
                        f"Medication analysis not performed: {med_analysis.get('message', 'No patient profile')}"
                    )

            except ImportError:
                logger.info("Medication analysis service not available")
                analysis["medication_analysis_completed"] = False
            except Exception as e:
                logger.error(f"Medication analysis failed: {str(e)}", exc_info=True)
                analysis["medication_analysis_completed"] = False

            return {
                "analysis_id": user_analysis.id,
                "mood_score": user_analysis.mood_score,
                "sentiment_score": user_analysis.sentiment_score,
                "emotions": user_analysis.dominant_emotions,
                "topics": user_analysis.topics_of_concern,
                "activities": user_analysis.suggested_activities,
                "risks": user_analysis.risk_factors,
                "improvements": user_analysis.improvement_metrics,
                "needs_attention": analysis.get("needs_attention", False),
                "recommendations_created": analysis.get("recommendations_created", 0),
            }

        except Exception as e:
            logger.error(f"Error analyzing user data: {str(e)}")
            return self._create_default_analysis()

    def _create_therapy_recommendations(self, user, analysis: Dict):
        """Create therapy recommendations based on analysis results"""
        try:
            from ..models import TherapyRecommendation

            recommendations_created = 0

            # Always create at least one activity recommendation from the default activities
            activities = analysis.get(
                "activities", ["journaling", "physical_activity", "breathing_exercises"]
            )

            # Create recommendations based on suggested activities
            for activity in activities[:3]:  # Limit to 3 activities
                if activity and activity not in ["general", "neutral"]:
                    TherapyRecommendation.objects.create(
                        user=user,
                        recommendation_type="activity_suggestion",
                        recommendation_data={
                            "activity": activity,
                            "priority": "medium",
                            "estimated_duration": "15-30 minutes",
                            "reason": "Based on analysis of mood patterns and journal entries",
                            "description": f"Try {activity.replace('_', ' ')} to improve your wellbeing",
                        },
                        context_data={
                            "mood_score": analysis.get("mood_score", 5),
                            "emotions": analysis.get("emotions", ["neutral"]),
                            "analysis_date": timezone.now().isoformat(),
                            "trigger_reason": "routine_analysis",
                        },
                    )
                    recommendations_created += 1

            # Create a general coping strategy recommendation
            TherapyRecommendation.objects.create(
                user=user,
                recommendation_type="coping_strategy",
                recommendation_data={
                    "strategy": "Regular mood monitoring",
                    "description": "Continue tracking your mood and journal entries to maintain awareness of your mental health patterns",
                    "frequency": "Daily",
                    "benefits": [
                        "Self-awareness",
                        "Pattern recognition",
                        "Early intervention",
                    ],
                },
                context_data={
                    "mood_score": analysis.get("mood_score", 5),
                    "analysis_date": timezone.now().isoformat(),
                    "data_points": len(analysis.get("mood_data", []))
                    + len(analysis.get("journal_data", [])),
                },
            )
            recommendations_created += 1

            # Create intervention recommendations for concerning patterns
            topics = analysis.get("topics", [])
            emotions = analysis.get("emotions", [])

            # Check for stress/anxiety patterns
            if any(
                term in str(topics + emotions).lower()
                for term in ["stress", "anxiety", "worried", "nervous"]
            ):
                TherapyRecommendation.objects.create(
                    user=user,
                    recommendation_type="intervention",
                    recommendation_data={
                        "intervention": "Stress and anxiety management",
                        "techniques": [
                            "Deep breathing exercises (4-7-8 technique)",
                            "Progressive muscle relaxation",
                            "Mindfulness meditation",
                            "Regular physical exercise",
                        ],
                        "priority": "high",
                        "description": "Addressing detected stress and anxiety patterns",
                    },
                    context_data={
                        "detected_patterns": ["stress", "anxiety"],
                        "emotions": emotions,
                        "topics": topics,
                        "analysis_date": timezone.now().isoformat(),
                    },
                )
                recommendations_created += 1

            # Check for sleep-related issues
            if any(
                term in str(topics).lower()
                for term in ["sleep", "tired", "exhausted", "insomnia"]
            ):
                TherapyRecommendation.objects.create(
                    user=user,
                    recommendation_type="coping_strategy",
                    recommendation_data={
                        "strategy": "Sleep hygiene improvement",
                        "description": "Focus on establishing better sleep patterns for improved mental health",
                        "specific_actions": [
                            "Maintain consistent sleep schedule",
                            "Create relaxing bedtime routine",
                            "Limit screen time before bed",
                            "Avoid caffeine late in the day",
                        ],
                        "expected_outcome": "Better sleep quality and mood regulation",
                    },
                    context_data={
                        "triggered_by": "sleep_concerns_detected",
                        "analysis_date": timezone.now().isoformat(),
                        "concern_level": "medium",
                    },
                )
                recommendations_created += 1

            analysis["recommendations_created"] = recommendations_created
            logger.info(
                f"Created {recommendations_created} therapy recommendations for user {user.id}"
            )

        except Exception as e:
            logger.error(
                f"Error creating therapy recommendations: {str(e)}", exc_info=True
            )
            analysis["recommendations_created"] = 0

    def _get_health_metrics(self, user, days: int) -> List[Dict]:
        """Get user's health metrics for analysis"""
        # Implementation placeholder - would pull from health metrics model
        return []

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Analyze data with Ollama model"""
        # Create a prompt from the data
        prompt = self._create_analysis_prompt(data)

        try:
            response = self.generate_text(prompt)
            # Parse the response into structured analysis
            analysis = self._parse_analysis_response(response["text"])
            return analysis
        except Exception as e:
            logger.error(f"Error in AI analysis: {str(e)}")
            return self._create_default_analysis()

    def _create_analysis_prompt(self, data: Dict) -> str:
        """Create a prompt for user data analysis"""
        prompt = "Analyze the following user data and provide insights:\n\n"

        if data.get("mood_logs"):
            prompt += "Mood logs:\n"
            for log in data["mood_logs"][:5]:  # Limit to 5 entries
                prompt += f"- Mood: {log['mood']}, Date: {log['timestamp']}\n"

        if data.get("journal_entries"):
            prompt += "\nJournal entries:\n"
            for entry in data["journal_entries"][:3]:  # Limit to 3 entries
                prompt += (
                    f"- Entry: {entry['content'][:100]}..., Mood: {entry['mood']}\n"
                )

        prompt += "\nProvide a structured analysis with these fields:\n"
        prompt += (
            "1. mood_score (0-10, where 0 is very negative, 10 is very positive)\n"
        )
        prompt += "2. sentiment_score (-1 to 1, where -1 is negative, 1 is positive)\n"
        prompt += "3. emotions (list of key emotions detected)\n"
        prompt += "4. topics (list of topics of concern or focus areas)\n"
        prompt += "5. activities (specific therapeutic activities recommended - be specific like 'mindfulness_meditation', 'journaling', 'physical_exercise', 'breathing_exercises')\n"
        prompt += "6. risks (any risk factors noted with severity levels)\n"
        prompt += "7. improvements (areas showing improvement)\n"
        prompt += (
            "8. needs_attention (boolean for whether immediate attention is needed)\n\n"
        )
        prompt += "Focus on providing actionable, specific recommendations based on the user's mood patterns and journal content."

        return prompt

    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse AI response into structured analysis"""
        analysis = {
            "mood_score": 5,  # Default values
            "sentiment_score": 0,
            "emotions": ["neutral"],
            "topics": [],
            "activities": ["journaling", "physical_activity", "breathing_exercises"],
            "risks": {},
            "improvements": {},
            "needs_attention": False,
        }

        try:
            import re

            # Try to parse mood score
            mood_match = re.search(
                r"mood_score[:\s]*(\d+)", response_text, re.IGNORECASE
            )
            if mood_match:
                analysis["mood_score"] = int(mood_match.group(1))

            # Try to parse emotions
            emotions_match = re.search(
                r"emotions[:\s]*\[(.*?)\]", response_text, re.IGNORECASE | re.DOTALL
            )
            if emotions_match:
                emotions_str = emotions_match.group(1)
                emotions = [
                    e.strip().strip("\"'") for e in emotions_str.split(",") if e.strip()
                ]
                if emotions:
                    analysis["emotions"] = emotions

            # Try to parse activities
            activities_match = re.search(
                r"activities[:\s]*\[(.*?)\]", response_text, re.IGNORECASE | re.DOTALL
            )
            if activities_match:
                activities_str = activities_match.group(1)
                activities = [
                    a.strip().strip("\"'")
                    for a in activities_str.split(",")
                    if a.strip()
                ]
                if activities:
                    analysis["activities"] = activities

            # Check for attention keywords
            attention_keywords = [
                "urgent",
                "concerning",
                "risk",
                "danger",
                "immediate",
                "crisis",
            ]
            if any(keyword in response_text.lower() for keyword in attention_keywords):
                analysis["needs_attention"] = True

        except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")

        return analysis

    def _create_default_analysis(self) -> Dict:
        """Create a default analysis when data is insufficient"""
        return {
            "mood_score": 5,
            "sentiment_score": 0,
            "emotions": ["neutral"],
            "topics": [],
            "activities": ["journaling", "physical activity"],
            "risks": {},
            "improvements": {},
            "needs_attention": False,
        }

    def _get_mood_data(self, user, days: int) -> List[Dict]:
        """Get user's mood data for analysis"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Use correct field name for mood logs
        mood_logs = MoodLog.objects.filter(
            user=user, logged_at__range=(start_date, end_date)
        ).order_by("-logged_at")

        return [
            {
                "mood": log.mood_rating,
                "activities": getattr(log, "activities", []),
                "timestamp": log.logged_at.isoformat(),
                "notes": getattr(log, "notes", ""),
            }
            for log in mood_logs
        ]

    def analyze_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a therapy session using AI.

        Args:
            session_data: Dictionary containing session information

        Returns:
            Dictionary containing analysis results
        """
        try:
            if not self.api_key or not self.api_endpoint:
                logger.error("AI service not properly configured")
                return {"error": "AI service configuration missing"}

            # Prepare the data for analysis
            analysis_data = self._prepare_session_data(session_data)

            # Make API request
            response = requests.post(
                f"{self.api_endpoint}/analyze",
                json=analysis_data,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"AI analysis failed: {response.text}")
                return {"error": "Analysis failed", "status": response.status_code}

        except Exception as e:
            logger.error(f"Error in analyze_session: {str(e)}")
            return {"error": str(e)}

    def _prepare_session_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare session data for AI analysis."""
        return {
            "session_id": session_data.get("id"),
            "timestamp": timezone.now().isoformat(),
            "content": session_data.get("content", ""),
            "metadata": session_data.get("metadata", {}),
        }

    def get_recommendations(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get AI-powered recommendations for a user.

        Args:
            user_data: Dictionary containing user information

        Returns:
            List of recommendation dictionaries
        """
        try:
            if not self.api_key or not self.api_endpoint:
                logger.error("AI service not properly configured")
                return []

            response = requests.post(
                f"{self.api_endpoint}/recommendations",
                json=user_data,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code == 200:
                return response.json().get("recommendations", [])
            else:
                logger.error(f"Failed to get recommendations: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error in get_recommendations: {str(e)}")
            return []


# Create a singleton instance
ai_service = AIAnalysisService()

# Export the singleton instance
__all__ = ["ai_service"]

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

            # Get mood logs
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
                        "activities": entry.activities,
                        "timestamp": entry.created_at.isoformat(),
                    }
                    for entry in journal_entries
                ],
                "health_metrics": health_metrics,
            }

            # Get analysis from Ollama
            analysis = self._analyze_with_ollama(data)

            # Store analysis results but don't assign to unused variable
            UserAnalysis.objects.create(
                user=user,
                mood_score=analysis.get("mood_score", 0),
                sentiment_score=analysis.get("sentiment_score", 0),
                dominant_emotions=analysis.get("emotions", []),
                topics_of_concern=analysis.get("topics", []),
                suggested_activities=analysis.get("activities", []),
                risk_factors=analysis.get("risks", {}),
                improvement_metrics=analysis.get("improvements", {}),
                health_metrics_correlation=analysis.get("health_correlations", {}),
            )

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

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing user data: {str(e)}")
            return self._create_default_analysis()

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
        prompt += "1. mood_score (0-10)\n"
        prompt += "2. sentiment_score (-1 to 1)\n"
        prompt += "3. emotions (list of key emotions)\n"
        prompt += "4. topics (list of topics of concern)\n"
        prompt += "5. activities (suggested activities)\n"
        prompt += "6. risks (any risk factors noted)\n"
        prompt += "7. improvements (areas showing improvement)\n"

        return prompt

    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse AI response into structured analysis"""
        analysis = {
            "mood_score": 5,  # Default values
            "sentiment_score": 0,
            "emotions": [],
            "topics": [],
            "activities": [],
            "risks": {},
            "improvements": {},
            "needs_attention": False,
        }

        try:
            import re

            mood_match = re.search(
                r"mood_score[:\s]*(\d+)", response_text, re.IGNORECASE
            )
            if mood_match:
                analysis["mood_score"] = int(mood_match.group(1))
        except Exception as e:
            logger.error(f"Error parsing mood score: {str(e)}")
            pass

        # More parsing logic would go here

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
            "health_correlations": {},
            "needs_attention": False,
        }

    def _get_mood_data(self, user, days: int) -> List[Dict]:
        """Get user's mood data for analysis"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        mood_logs = MoodLog.objects.filter(
            user=user, logged_at__range=(start_date, end_date)
        ).order_by("-logged_at")

        return [
            {
                "mood": log.mood_rating,
                "activities": log.activities,
                "timestamp": log.logged_at.isoformat(),
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

#AI_engine/services/ai_analysis.py
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
    def __init__(self):
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
                    }
                }
            else:
                logger.error(f"Ollama request failed with status {response.status_code}")
                raise Exception(f"Ollama request failed with status {response.status_code}")

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
            }

            # Get analysis from Ollama
            analysis = self._analyze_with_ollama(data)

            # Save analysis results
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

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Analyze data using Ollama"""
        try:
            prompt = self._build_analysis_prompt(data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_analysis_response(result["response"])
            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                return self._create_default_analysis()

        except Exception as e:
            logger.error(f"Error in Ollama analysis: {str(e)}")
            return self._create_default_analysis()

    def _build_analysis_prompt(self, data: Dict) -> str:
        """Build prompt for Ollama analysis"""
        return f"""As an AI analyst, analyze the following user data and provide insights:

Mood History: {data['mood_logs']}
Journal Entries: {data['journal_entries']}

Analyze this data and provide insights in JSON format with these fields:
{{
    "mood_score": <float between -1 and 1>,
    "sentiment_score": <float between -1 and 1>,
    "emotions": [<list of dominant emotions>],
    "topics": [<list of main topics or concerns>],
    "activities": [<list of suggested activities>],
    "risks": {{<risk factors and their levels>}},
    "improvements": {{<improvement metrics>}},
    "needs_attention": <boolean indicating if immediate attention is needed>
}}"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse and validate Ollama's analysis response"""
        try:
            import json

            analysis = json.loads(response)

            required_fields = [
                "mood_score",
                "sentiment_score",
                "emotions",
                "topics",
                "activities",
                "risks",
                "improvements",
                "needs_attention",
            ]

            # Ensure all required fields exist
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = self._create_default_analysis()[field]

            return analysis

        except json.JSONDecodeError:
            logger.error("Failed to parse Ollama analysis response as JSON")
            return self._create_default_analysis()
        except Exception as e:
            logger.error(f"Error processing Ollama analysis: {str(e)}")
            return self._create_default_analysis()

    def _create_default_analysis(self) -> Dict:
        """Create a default analysis when AI analysis fails"""
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


# Create singleton instance
ai_service = AIAnalysisService()

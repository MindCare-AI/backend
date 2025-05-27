# AI_engine/services.py
from typing import Dict, Any, List
import logging
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json

from .models import UserAnalysis, AIInsight
from mood.models import MoodLog
from journal.models import JournalEntry

logger = logging.getLogger(__name__)


class OllamaModelManager:
    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        self.required_models = ["llama2", "mistral"]  # Models we'll use

    def check_model_status(self) -> Dict[str, bool]:
        """Check if required models are installed"""
        try:
            response = requests.get(f"{self.base_url}/tags")
            if response.status_code == 200:
                installed_models = [
                    model["name"] for model in response.json()["models"]
                ]
                return {
                    model: model in installed_models for model in self.required_models
                }
            return {model: False for model in self.required_models}
        except Exception as e:
            logger.error(f"Error checking model status: {str(e)}")
            return {model: False for model in self.required_models}

    def install_model(self, model_name: str) -> bool:
        """Install a specific model"""
        try:
            response = requests.post(f"{self.base_url}/pull", json={"name": model_name})
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error installing model {model_name}: {str(e)}")
            return False

    def ensure_models_installed(self) -> bool:
        """Check and install missing models"""
        status = self.check_model_status()
        success = True

        for model, installed in status.items():
            if not installed:
                logger.info(f"Installing missing model: {model}")
                if not self.install_model(model):
                    success = False
                    logger.error(f"Failed to install model: {model}")

        return success


class AIAnalysisService:
    def __init__(self):
        # Safely get settings with defaults
        self.base_url = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434')
        self.default_model = "mistral"
        self.initialized = False
        
        # Get AI engine settings with defaults
        ai_settings = getattr(settings, 'AI_ENGINE_SETTINGS', {})
        self.batch_size = ai_settings.get('ANALYSIS_BATCH_SIZE', 50)
        self.max_period = ai_settings.get('MAX_ANALYSIS_PERIOD', 90)
        self.min_data_points = ai_settings.get('MIN_DATA_POINTS', 5)
        self.risk_threshold = ai_settings.get('RISK_THRESHOLD', 0.7)

    def initialize(self) -> bool:
        """Initialize the AI service and ensure required models are available"""
        try:
            # Check if Ollama is accessible
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                logger.error("Cannot connect to Ollama API")
                return False

            # Check if required model is available
            model_response = requests.get(
                f"{self.base_url}/api/show", params={"name": self.default_model}
            )
            if model_response.status_code == 404:
                logger.info(
                    f"Model {self.default_model} not found, attempting to pull..."
                )
                pull_response = requests.post(
                    f"{self.base_url}/api/pull", json={"name": self.default_model}
                )
                if pull_response.status_code != 200:
                    logger.error(f"Failed to pull model {self.default_model}")
                    return False

            self.initialized = True
            logger.info("AI Analysis Service initialized successfully")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to initialize AI service: {str(e)}")
            return False

    def analyze_user_data(self, user, date_range=30) -> Dict[str, Any]:
        """Analyze user's mood and journal data for insights"""
        if not self.initialized:
            logger.error("AI service not initialized")
            return None

        try:
            # Get user data
            mood_data = self._get_mood_data(user, date_range)
            journal_data = self._get_journal_data(user, date_range)

            if not mood_data and not journal_data:
                return self._create_default_analysis()

            # Analyze using Ollama
            analysis = self._analyze_with_ollama(mood_data, journal_data)

            # Create analysis record
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
                self._generate_insights(user, analysis)

            return user_analysis

        except Exception as e:
            logger.error(f"Error analyzing user data: {str(e)}")
            return None

    def _get_mood_data(self, user, days: int) -> List[Dict]:
        """Get user's mood data for analysis"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Use correct field name for timestamp
        mood_logs = MoodLog.objects.filter(
            user=user, logged_at__range=(start_date, end_date)
        ).order_by("-logged_at")

        return [
            {
                "mood": log.mood_rating,
                "activities": getattr(log, 'activities', []),
                "timestamp": log.logged_at.isoformat(),
                "notes": getattr(log, 'notes', ''),
            }
            for log in mood_logs
        ]

    def _get_journal_data(self, user, days: int) -> List[Dict]:
        """Get user's journal data for analysis"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        entries = JournalEntry.objects.filter(
            user=user, created_at__range=(start_date, end_date)
        ).order_by("-created_at")

        return [
            {
                "content": entry.content,
                "mood": entry.mood,
                "activities": entry.activities,
                "timestamp": entry.created_at.isoformat(),
            }
            for entry in entries
        ]

    def _analyze_with_ollama(
        self, mood_data: List[Dict], journal_data: List[Dict]
    ) -> Dict:
        """Analyze data using Ollama"""
        if not self.initialized:
            logger.error("AI service not initialized")
            return self._create_default_analysis()

        try:
            prompt = self._build_analysis_prompt(mood_data, journal_data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.default_model, "prompt": prompt, "stream": False},
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

    def _build_analysis_prompt(
        self, mood_data: List[Dict], journal_data: List[Dict]
    ) -> str:
        """Build prompt for AI analysis"""
        return f"""As a mental health analysis system, analyze the following user data:

Mood History: {mood_data}
Journal Entries: {journal_data}

Analyze this data and provide insights on:
1. Overall mood trend and emotional patterns
2. Key themes or topics of concern
3. Risk factors or warning signs
4. Suggested activities or interventions
5. Progress indicators and improvements

Format your response as a JSON object with these fields:
{{
    "mood_score": <float between -1 and 1>,
    "sentiment_score": <float between -1 and 1>,
    "emotions": [<list of dominant emotions>],
    "topics": [<list of main topics or concerns>],
    "activities": [<list of suggested activities>],
    "risks": {{<risk factors and their levels>}},
    "improvements": {{<improvement metrics>}},
    "needs_attention": <boolean>
}}"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse and validate the AI analysis response"""
        try:
            analysis = json.loads(response)

            # Ensure all required fields are present
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

            for field in required_fields:
                if field not in analysis:
                    analysis[field] = self._create_default_analysis()[field]

            return analysis

        except json.JSONDecodeError:
            logger.error("Failed to parse AI analysis response as JSON")
            return self._create_default_analysis()
        except Exception as e:
            logger.error(f"Error processing AI analysis: {str(e)}")
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

    def _generate_insights(self, user, analysis: Dict):
        """Generate insights based on analysis"""
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


# Create singleton instance
ai_service = AIAnalysisService()

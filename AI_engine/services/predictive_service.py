# AI_engine/services/predictive_service.py
import logging
from typing import Dict, Any
import requests
from django.utils import timezone
from datetime import timedelta
from journal.models import JournalEntry
from django.db.models import Avg, Case, When, FloatField

logger = logging.getLogger(__name__)


class PredictiveAnalysisService:
    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        self.model = "mistral"  # Using Mistral for predictive analysis

    def predict_mood_decline(self, user, timeframe_days: int = 7) -> Dict:
        """Predict potential mood declines based on patterns"""
        from mood.models import MoodLog

        # Get historical mood data
        mood_logs = MoodLog.objects.filter(
            user=user, logged_at__gte=timezone.now() - timedelta(days=timeframe_days)
        ).order_by("logged_at")

        if not mood_logs.exists():
            return {"risk_level": "unknown", "confidence": 0, "factors": []}

        # Prepare data for analysis
        mood_data = [
            {
                "rating": log.mood_rating,
                "activities": log.activities,
                "timestamp": log.logged_at.isoformat(),  # Keep using 'timestamp' in the data structure
            }
            for log in mood_logs
        ]

        # Create analysis prompt
        prompt = f"""Analyze this mood data and predict the likelihood of mood decline:
        {mood_data}
        
        Provide analysis in JSON format:
        {{
            "risk_level": "low|medium|high",
            "confidence": <float 0-1>,
            "factors": [<list of contributing factors>],
            "recommendations": [<list of preventive actions>]
        }}
        """

        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                return response.json().get("response", {})
            return {"risk_level": "unknown", "confidence": 0, "factors": []}

        except Exception as e:
            logger.error(f"Error in mood decline prediction: {str(e)}")
            return {"risk_level": "unknown", "confidence": 0, "factors": []}

    def predict_therapy_outcomes(self, user, timeframe_days: int = 30) -> Dict:
        """Predict therapy outcomes based on user engagement and progress"""
        from journal.models import JournalEntry
        from appointments.models import Appointment
        from mood.models import MoodLog

        end_date = timezone.now()
        start_date = end_date - timedelta(days=timeframe_days)

        # Gather data from multiple sources
        data = {
            "journal_entries": JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).count(),
            "mood_logs": MoodLog.objects.filter(
                user=user, timestamp__range=(start_date, end_date)
            ).count(),
            "appointments": Appointment.objects.filter(
                patient=user, scheduled_time__range=(start_date, end_date)
            ).count(),
            "appointment_attendance": Appointment.objects.filter(
                patient=user,
                scheduled_time__range=(start_date, end_date),
                status="completed",
            ).count(),
        }

        prompt = f"""Analyze therapy engagement data and predict outcomes:
        {data}
        
        Provide analysis in JSON format:
        {{
            "engagement_level": "low|medium|high",
            "predicted_outcome": "improving|stable|declining",
            "confidence": <float 0-1>,
            "recommendations": [<list of recommendations>]
        }}
        """

        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                return response.json().get("response", {})
            return {"engagement_level": "unknown", "confidence": 0}

        except Exception as e:
            logger.error(f"Error in therapy outcome prediction: {str(e)}")
            return {"engagement_level": "unknown", "confidence": 0}

    def analyze_journal_patterns(self, user, time_field="created_at", **kwargs) -> Dict:
        """Analyze patterns in journal entries to identify themes and concerns"""
        now = timezone.now()
        month_ago = now - timedelta(days=30)

        qs = JournalEntry.objects.filter(user=user, **{f"{time_field}__gte": month_ago})

        # Map valid 'mood' field choices to numeric values for aggregation
        avg_mood = (
            qs.aggregate(
                avg_mood=Avg(
                    Case(
                        When(mood="very_negative", then=1.0),
                        When(mood="negative", then=2.0),
                        When(mood="neutral", then=3.0),
                        When(mood="positive", then=4.0),
                        When(mood="very_positive", then=5.0),
                        default=3.0,
                        output_field=FloatField(),
                    )
                )
            )["avg_mood"]
            or 3.0
        )

        analysis = {
            "concerns": qs.exists(),  # Dummy flag; update with real logic as needed
            "sentiment_trend": "neutral",  # Placeholder value
            "avg_mood": avg_mood,
        }

        return analysis


# Create singleton instance
predictive_service = PredictiveAnalysisService()


def predict_next_appointment(user) -> Dict[str, Any]:
    """Predict optimal next appointment time based on user history"""
    try:
        # Implementation using Ollama API will go here
        return {"success": True, "prediction": "Next week", "confidence": 0.8}
    except Exception as e:
        logger.error(f"Error in appointment prediction: {str(e)}")
        return {"success": False, "error": str(e)}


def predict_next_journal_entry(user) -> Dict[str, Any]:
    """Analyze journal patterns and predict future entries"""
    try:
        return {
            "success": True,
            "sentiment_trend": "improving",
            "predicted_topics": ["anxiety", "progress"],
        }
    except Exception as e:
        logger.error(f"Error in journal prediction: {str(e)}")
        return {"success": False, "error": str(e)}


def analyze_journal_patterns(user) -> Dict[str, Any]:
    """Analyze patterns in user's journal entries"""
    try:
        return {
            "success": True,
            "sentiment_trend": "improving",
            "concerns": [],
            "topics": ["anxiety", "progress"],
        }
    except Exception as e:
        logger.error(f"Error analyzing journal patterns: {str(e)}")
        return {"success": False, "error": str(e)}

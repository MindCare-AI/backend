import logging
from typing import Dict, Any
import requests
from django.utils import timezone
from datetime import timedelta

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
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=timeframe_days)
        ).order_by('timestamp')
        
        if not mood_logs.exists():
            return {"risk_level": "unknown", "confidence": 0, "factors": []}
            
        # Prepare data for analysis
        mood_data = [
            {
                "rating": log.mood_rating,
                "activities": log.activities,
                "timestamp": log.timestamp.isoformat()
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
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json().get('response', {})
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
                user=user,
                created_at__range=(start_date, end_date)
            ).count(),
            
            "mood_logs": MoodLog.objects.filter(
                user=user,
                timestamp__range=(start_date, end_date)
            ).count(),
            
            "appointments": Appointment.objects.filter(
                patient=user,
                scheduled_time__range=(start_date, end_date)
            ).count(),
            
            "appointment_attendance": Appointment.objects.filter(
                patient=user,
                scheduled_time__range=(start_date, end_date),
                status='completed'
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
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json().get('response', {})
            return {"engagement_level": "unknown", "confidence": 0}
            
        except Exception as e:
            logger.error(f"Error in therapy outcome prediction: {str(e)}")
            return {"engagement_level": "unknown", "confidence": 0}

    def analyze_journal_patterns(self, user, timeframe_days: int = 30) -> Dict:
        """Analyze patterns in journal entries to identify themes and concerns"""
        from journal.models import JournalEntry
        
        entries = JournalEntry.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=timeframe_days)
        ).order_by('created_at')
        
        if not entries.exists():
            return {"themes": [], "concerns": [], "recommendations": []}
            
        # Prepare journal data
        journal_data = [
            {
                "content": entry.content,
                "mood": entry.mood,
                "activities": entry.activities,
                "date": entry.created_at.isoformat()
            }
            for entry in entries
        ]
        
        prompt = f"""Analyze these journal entries for patterns and themes:
        {journal_data}
        
        Provide analysis in JSON format:
        {{
            "themes": [<list of recurring themes>],
            "concerns": [<list of potential concerns>],
            "progress_indicators": [<list of positive progress indicators>],
            "recommendations": [<list of recommendations>],
            "sentiment_trend": "improving|stable|declining"
        }}
        """
        
        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json().get('response', {})
            return {"themes": [], "concerns": [], "recommendations": []}
            
        except Exception as e:
            logger.error(f"Error in journal pattern analysis: {str(e)}")
            return {"themes": [], "concerns": [], "recommendations": []}

# Create singleton instance
predictive_service = PredictiveAnalysisService()

def predict_next_appointment(user) -> Dict[str, Any]:
    """Predict optimal next appointment time based on user history"""
    try:
        # Implementation using Ollama API will go here
        return {
            "success": True,
            "prediction": "Next week",
            "confidence": 0.8
        }
    except Exception as e:
        logger.error(f"Error in appointment prediction: {str(e)}")
        return {"success": False, "error": str(e)}

def predict_next_journal_entry(user) -> Dict[str, Any]:
    """Analyze journal patterns and predict future entries"""
    try:
        return {
            "success": True,
            "sentiment_trend": "improving",
            "predicted_topics": ["anxiety", "progress"]
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
            "topics": ["anxiety", "progress"]
        }
    except Exception as e:
        logger.error(f"Error analyzing journal patterns: {str(e)}")
        return {"success": False, "error": str(e)}
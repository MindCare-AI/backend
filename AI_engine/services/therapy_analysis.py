from typing import Dict, Any
import logging
from django.conf import settings
import requests

logger = logging.getLogger(__name__)

class TherapyAnalysisService:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"

    def analyze_therapy_session(self, session_notes: str) -> Dict[str, Any]:
        """Analyze therapy session notes for insights"""
        try:
            prompt = f"""Analyze these therapy session notes and provide insights:
            {session_notes}
            
            Provide analysis in JSON format:
            {{
                "key_themes": [<list of main themes>],
                "progress_indicators": [<list of progress indicators>],
                "concerns": [<list of concerns>],
                "recommendations": [<list of recommendations>]
            }}
            """
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json().get('response', {})
            return {"success": False, "error": "API request failed"}
            
        except Exception as e:
            logger.error(f"Error in therapy session analysis: {str(e)}")
            return {"success": False, "error": str(e)}

# Create singleton instance
therapy_analysis = TherapyAnalysisService()

def analyze_therapy(session_notes: str) -> Dict[str, Any]:
    """Analyze therapy session using the service"""
    return therapy_analysis.analyze_therapy_session(session_notes)
# AI_engine/services/medication_analysis.py
from typing import Dict, Any
import logging
from django.conf import settings
import requests
from django.utils import timezone
from datetime import timedelta
from ..models import MedicationEffectAnalysis, AIInsight

logger = logging.getLogger(__name__)


class MedicationAnalysisService:
    """Service to analyze medication effects on mood and behavior."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.analysis_period = 30  # Default analysis period in days

    def analyze_medication_effects(self, user, days: int = None) -> Dict[str, Any]:
        """
        Analyze the effects of medications on a user's mood and behavior.

        This tracks:
        - Temporal relationships between medication changes and mood
        - Potential side effects detected in journal entries or mood logs
        - Adherence patterns based on reported usage
        """
        try:
            analysis_period = days or self.analysis_period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=analysis_period)

            # Import here to avoid circular imports
            from mood.models import MoodLog
            from journal.models import JournalEntry
            from patient.models.patient_profile import PatientProfile

            # Get the user's patient profile
            try:
                patient_profile = PatientProfile.objects.get(user=user)
                current_medications = patient_profile.current_medications or []
            except PatientProfile.DoesNotExist:
                # If no patient profile exists, we can't analyze medications
                return {"error": "No patient profile found", "success": False}

            # Check if we have medication data
            if not current_medications:
                return {
                    "success": True,
                    "message": "No medications to analyze",
                    "medications": [],
                }

            # Get mood logs for the period
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            # Get journal entries that might mention medications
            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("created_at")

            # Prepare data for analysis
            mood_data = [
                {
                    "mood_rating": log.mood_rating,
                    "logged_at": log.logged_at.isoformat(),
                    "activities": log.activities,
                    "notes": log.notes if hasattr(log, "notes") else "",
                }
                for log in mood_logs
            ]

            journal_data = [
                {
                    "content": entry.content,
                    "mood": entry.mood,
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in journal_entries
            ]

            # Combine data for analysis
            analysis_data = {
                "medications": current_medications,
                "mood_data": mood_data,
                "journal_data": journal_data,
            }

            # Use Ollama to analyze medication effects
            analysis = self._analyze_with_ollama(analysis_data)

            # Save the analysis results
            med_analysis = MedicationEffectAnalysis.objects.create(
                user=user,
                analysis_date=timezone.now().date(),
                medications=current_medications,
                mood_effects=analysis.get("mood_effects", {}),
                side_effects_detected=analysis.get("side_effects_detected", []),
                adherence_patterns=analysis.get("adherence_patterns", {}),
                recommendations=analysis.get("recommendations", []),
            )

            # Generate insights if significant side effects or issues are detected
            if analysis.get("needs_attention"):
                AIInsight.objects.create(
                    user=user,
                    insight_type="medication_effect",
                    insight_data={
                        "medications": [
                            m for m in analysis.get("medications_of_concern", [])
                        ],
                        "description": analysis.get("concern_description", ""),
                        "recommendations": analysis.get("recommendations", []),
                    },
                    priority=analysis.get("priority_level", "medium"),
                )

            return {
                "success": True,
                "analysis_id": med_analysis.id,
                "medications": current_medications,
                "mood_effects": analysis.get("mood_effects", {}),
                "side_effects_detected": analysis.get("side_effects_detected", []),
                "adherence_patterns": analysis.get("adherence_patterns", {}),
                "recommendations": analysis.get("recommendations", []),
                "needs_attention": analysis.get("needs_attention", False),
            }

        except Exception as e:
            logger.error(f"Error analyzing medication effects: {str(e)}", exc_info=True)
            return {"error": str(e), "success": False}

    def _analyze_with_ollama(self, data: Dict) -> Dict[str, Any]:
        """Analyze medication effects using Ollama"""
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
        """Build prompt for Ollama medication analysis"""
        medications = data.get("medications", [])
        mood_data_sample = data.get("mood_data", [])[
            :10
        ]  # Limit to 10 entries for prompt size
        journal_samples = [
            entry
            for entry in data.get("journal_data", [])[:5]
            if any(
                med.lower() in entry.get("content", "").lower() for med in medications
            )
        ]

        return f"""As a mental health AI assistant, analyze the following data to identify potential medication effects:

Current Medications: {medications}

Mood Data Sample: {mood_data_sample}

Journal Entries Mentioning Medications: {journal_samples}

Analyze this data to identify:
1. Effects of medications on mood
2. Potential side effects mentioned in journal entries
3. Patterns of medication adherence
4. Any concerning effects that should be addressed

Provide analysis in JSON format with these fields:
{{
    "mood_effects": {{<analysis of how each medication appears to affect mood>}},
    "side_effects_detected": [<list of potential side effects detected>],
    "adherence_patterns": {{<analysis of medication adherence patterns>}},
    "recommendations": [<list of recommendations>],
    "needs_attention": <boolean indicating if there are concerning effects>,
    "priority_level": <"low", "medium", or "high" if needs attention>,
    "medications_of_concern": [<list of medications with concerning effects>],
    "concern_description": <description of the concerning effects if any>
}}"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse and validate Ollama's analysis response"""
        try:
            import json

            # Try to extract the JSON portion of the response
            if "```json" in response and "```" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                analysis = json.loads(json_str)
            elif "```" in response and "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                analysis = json.loads(json_str)
            else:
                analysis = json.loads(response)

            required_fields = [
                "mood_effects",
                "side_effects_detected",
                "adherence_patterns",
                "recommendations",
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
            "mood_effects": {"general": "unknown"},
            "side_effects_detected": [],
            "adherence_patterns": {"consistency": "unknown"},
            "recommendations": ["Continue monitoring medication effects"],
            "needs_attention": False,
        }

    def track_medication_changes(self, user, days: int = 90) -> Dict[str, Any]:
        """
        Track changes in medications over time and correlate with mood changes

        This helps identify temporal relationships between medication changes
        and significant mood shifts
        """
        try:
            from mood.models import MoodLog
            from journal.models import JournalEntry

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Get journal entries that mention medication changes
            entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("created_at")

            # Get mood logs for correlation
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            # Extract medication change mentions from entries
            medication_changes = []
            common_med_terms = [
                "medication",
                "medicine",
                "prescribed",
                "started",
                "stopped",
                "dose",
                "dosage",
            ]

            for entry in entries:
                content = entry.content.lower()
                if any(term in content for term in common_med_terms):
                    # Simple heuristic to detect medication changes
                    medication_changes.append(
                        {
                            "date": entry.created_at.date().isoformat(),
                            "content": entry.content,
                            "mood": entry.mood,
                        }
                    )

            # Track mood changes around medication changes
            mood_tracking = {}
            for mood in mood_logs:
                date = mood.logged_at.date().isoformat()
                if date not in mood_tracking:
                    mood_tracking[date] = {"ratings": [], "medications": set()}
                mood_tracking[date]["ratings"].append(mood.mood_rating)

            # Calculate average mood per day and track medication changes
            for change in medication_changes:
                date = change["date"]
                if date in mood_tracking:
                    mood_tracking[date]["medications"].update(
                        [
                            m.strip()
                            for m in change.get("content", "").split(",")
                            if m.strip()
                        ]
                    )

            # Create analysis result
            analysis_result = {
                "medication_changes": medication_changes,
                "mood_tracking": mood_tracking,
            }

            # Analyze mood trends around medication changes
            trend_analysis = self._analyze_mood_trends(
                mood_tracking, medication_changes
            )

            analysis_result.update(
                {
                    "mood_trends": trend_analysis.get("trends", {}),
                    "correlation_score": trend_analysis.get("correlation_score", 0),
                    "significant_changes": trend_analysis.get(
                        "significant_changes", []
                    ),
                }
            )

            return analysis_result

        except Exception as e:
            logger.error(f"Error tracking medication changes: {str(e)}", exc_info=True)
            return {"error": str(e), "success": False}


# Create singleton instance
medication_analysis_service = MedicationAnalysisService()

# AI_engine/services/medication_analysis.py
from typing import Dict, Any
import logging
from django.conf import settings
import requests
from django.utils import timezone
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
        Analyze the effects of medications on a user's mood and behavior using AI data interface.

        This tracks:
        - Temporal relationships between medication changes and mood
        - Potential side effects detected in journal entries or mood logs
        - Adherence patterns based on reported usage
        """
        try:
            analysis_period = days or self.analysis_period

            # Import AI data interface service
            from .data_interface import ai_data_interface

            # Import patient profile directly (non-data collection)
            from patient.models.patient_profile import PatientProfile

            # Get the user's patient profile for medication data
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

            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, analysis_period)

            # Check data quality and availability
            quality_metrics = dataset.get("quality_metrics", {})
            if quality_metrics.get("overall_quality", 0.0) < 0.1:
                logger.warning(
                    f"Insufficient data quality for user {user.id} medication analysis: {quality_metrics}"
                )
                return {
                    "success": True,
                    "message": "Insufficient data for meaningful medication analysis",
                    "medications": current_medications,
                    "data_quality_warning": True,
                }

            # Extract relevant data from AI-ready dataset for medication analysis
            analysis_data = self._prepare_medication_analysis_data(
                dataset, current_medications
            )

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

            # Enhanced result with datawarehouse integration metrics
            processing_metadata = dataset.get("processing_metadata", {})
            return {
                "success": True,
                "analysis_id": med_analysis.id,
                "medications": current_medications,
                "mood_effects": analysis.get("mood_effects", {}),
                "side_effects_detected": analysis.get("side_effects_detected", []),
                "adherence_patterns": analysis.get("adherence_patterns", {}),
                "recommendations": analysis.get("recommendations", []),
                "needs_attention": analysis.get("needs_attention", False),
                "data_integration": {
                    "data_sources_used": dataset.get("data_sources", []),
                    "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                    "completeness_score": quality_metrics.get("completeness", 0.0),
                    "analysis_recommendation": quality_metrics.get(
                        "analysis_recommendation", "unknown"
                    ),
                    "datawarehouse_version": processing_metadata.get(
                        "processing_version", "unknown"
                    ),
                    "collection_time": processing_metadata.get(
                        "collection_time_seconds", 0
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing medication effects: {str(e)}", exc_info=True)
            return {"error": str(e), "success": False}

    def _prepare_medication_analysis_data(
        self, dataset: Dict, current_medications: list
    ) -> Dict[str, Any]:
        """Prepare medication analysis data from AI-ready dataset"""
        try:
            mood_analytics = dataset.get("mood_analytics", {})
            journal_analytics = dataset.get("journal_analytics", {})

            # Extract mood data
            mood_data = []
            if mood_analytics.get("mood_entries"):
                mood_data = [
                    {
                        "mood_rating": entry.get("rating", entry.get("mood_rating", 5)),
                        "logged_at": entry.get("logged_at", entry.get("timestamp", "")),
                        "activities": entry.get("activities", []),
                        "notes": entry.get("notes", ""),
                        "date": entry.get("date", ""),
                        "time_of_day": entry.get("time_of_day", "unknown"),
                    }
                    for entry in mood_analytics["mood_entries"][
                        :20
                    ]  # Limit for analysis
                ]

            # Extract journal data, focusing on medication-related content
            journal_data = []
            if journal_analytics.get("journal_entries"):
                for entry in journal_analytics["journal_entries"][
                    :10
                ]:  # Limit for analysis
                    content = entry.get("content", "")
                    # Check if entry mentions medications
                    if any(
                        med.lower() in content.lower() for med in current_medications
                    ) or any(
                        term in content.lower()
                        for term in [
                            "medication",
                            "medicine",
                            "pill",
                            "dose",
                            "side effect",
                        ]
                    ):
                        journal_data.append(
                            {
                                "content": content,
                                "mood": entry.get("mood", "neutral"),
                                "created_at": entry.get(
                                    "created_at", entry.get("timestamp", "")
                                ),
                                "sentiment_score": entry.get("sentiment_score", 0.0),
                                "emotions": entry.get("emotions", {}),
                            }
                        )

            return {
                "medications": current_medications,
                "mood_data": mood_data,
                "journal_data": journal_data,
                "dataset_quality": dataset.get("quality_metrics", {}),
                "analysis_period": dataset.get("processing_metadata", {}).get(
                    "date_range", {}
                ),
            }

        except Exception as e:
            logger.error(f"Error preparing medication analysis data: {str(e)}")
            return {
                "medications": current_medications,
                "mood_data": [],
                "journal_data": [],
                "dataset_quality": {},
                "analysis_period": {},
            }

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
        Track changes in medications over time and correlate with mood changes using AI data interface

        This helps identify temporal relationships between medication changes
        and significant mood shifts
        """
        try:
            # Import AI data interface service
            from .data_interface import ai_data_interface

            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, days)

            # Check data quality and availability
            quality_metrics = dataset.get("quality_metrics", {})
            if quality_metrics.get("overall_quality", 0.0) < 0.1:
                logger.warning(
                    f"Insufficient data quality for user {user.id} medication tracking: {quality_metrics}"
                )
                return {
                    "success": True,
                    "message": "Insufficient data for meaningful medication tracking",
                    "data_quality_warning": True,
                }

            # Extract medication changes and mood tracking from AI-ready dataset
            tracking_data = self._extract_medication_tracking_data(dataset)

            # Analyze mood trends around medication changes
            trend_analysis = self._analyze_mood_trends(
                tracking_data["mood_tracking"], tracking_data["medication_changes"]
            )

            # Enhanced result with datawarehouse integration metrics
            processing_metadata = dataset.get("processing_metadata", {})
            analysis_result = {
                "success": True,
                "medication_changes": tracking_data["medication_changes"],
                "mood_tracking": tracking_data["mood_tracking"],
                "mood_trends": trend_analysis.get("trends", {}),
                "correlation_score": trend_analysis.get("correlation_score", 0),
                "significant_changes": trend_analysis.get("significant_changes", []),
                "data_integration": {
                    "data_sources_used": dataset.get("data_sources", []),
                    "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                    "completeness_score": quality_metrics.get("completeness", 0.0),
                    "analysis_recommendation": quality_metrics.get(
                        "analysis_recommendation", "unknown"
                    ),
                    "datawarehouse_version": processing_metadata.get(
                        "processing_version", "unknown"
                    ),
                    "collection_time": processing_metadata.get(
                        "collection_time_seconds", 0
                    ),
                },
            }

            return analysis_result

        except Exception as e:
            logger.error(f"Error tracking medication changes: {str(e)}", exc_info=True)
            return {"error": str(e), "success": False}

    def _extract_medication_tracking_data(self, dataset: Dict) -> Dict[str, Any]:
        """Extract medication tracking data from AI-ready dataset"""
        try:
            journal_analytics = dataset.get("journal_analytics", {})
            mood_analytics = dataset.get("mood_analytics", {})

            # Extract medication change mentions from journal entries
            medication_changes = []
            common_med_terms = [
                "medication",
                "medicine",
                "prescribed",
                "started",
                "stopped",
                "dose",
                "dosage",
                "pill",
                "tablet",
            ]

            if journal_analytics.get("journal_entries"):
                for entry in journal_analytics["journal_entries"]:
                    content = entry.get("content", "").lower()
                    if any(term in content for term in common_med_terms):
                        # Simple heuristic to detect medication changes
                        medication_changes.append(
                            {
                                "date": entry.get("date", entry.get("created_at", "")),
                                "content": entry.get("content", "")[
                                    :200
                                ],  # Limit content
                                "mood": entry.get("mood", "neutral"),
                                "sentiment_score": entry.get("sentiment_score", 0.0),
                            }
                        )

            # Track mood changes from mood analytics
            mood_tracking = {}
            if mood_analytics.get("mood_entries"):
                for mood_entry in mood_analytics["mood_entries"]:
                    date = mood_entry.get("date", "")
                    if date:
                        if date not in mood_tracking:
                            mood_tracking[date] = {"ratings": [], "medications": set()}
                        mood_tracking[date]["ratings"].append(
                            mood_entry.get("rating", mood_entry.get("mood_rating", 5))
                        )

            # Associate medication changes with mood tracking dates
            for change in medication_changes:
                date = (
                    change["date"][:10] if change["date"] else ""
                )  # Extract date part
                if date in mood_tracking:
                    # Extract potential medication names from content
                    content_words = [
                        word.strip()
                        for word in change.get("content", "").split(",")
                        if word.strip()
                    ]
                    mood_tracking[date]["medications"].update(
                        content_words[:5]
                    )  # Limit additions

            return {
                "medication_changes": medication_changes,
                "mood_tracking": mood_tracking,
            }

        except Exception as e:
            logger.error(f"Error extracting medication tracking data: {str(e)}")
            return {
                "medication_changes": [],
                "mood_tracking": {},
            }


# Create singleton instance
medication_analysis_service = MedicationAnalysisService()

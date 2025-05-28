# AI_engine/services/therapy_analysis.py
from typing import Dict, List, Any, Optional
import logging
import requests
import json
import re
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from ..models import TherapyRecommendation, AIInsight
import numpy as np

logger = logging.getLogger(__name__)


class TherapyAnalysisService:
    """Enhanced therapy analysis service for generating therapy session recommendations"""

    def __init__(self):
        self.base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self.model = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "DEFAULT_MODEL", "mistral"
        )
        self.cache_timeout = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "CACHE_TIMEOUT", 900
        )
        self.max_prompt_length = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "MAX_PROMPT_LENGTH", 4000
        )
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize the therapy analysis service"""
        try:
            # Check if Ollama is accessible
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.initialized = True
                logger.info("Therapy Analysis Service initialized successfully")
                return True
            else:
                logger.error("Cannot connect to Ollama API for therapy analysis")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize therapy analysis service: {str(e)}")
            return False

    def analyze_for_therapy_session(self, user, days: int = 7) -> Dict[str, Any]:
        """
        Comprehensive analysis for therapy session preparation

        Args:
            user: User object
            days: Number of days to analyze (default 7)

        Returns:
            Dict containing therapy session recommendations
        """
        cache_key = f"therapy_analysis_{user.id}_{days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            if not self.initialized and not self.initialize():
                return self._create_default_analysis()

            # Collect comprehensive user data
            user_data = self._collect_comprehensive_data(user, days)

            if not self._has_sufficient_data(user_data):
                return self._create_insufficient_data_response(user_data)

            # Generate therapy recommendations using AI
            analysis = self._analyze_with_ollama(user_data)

            # Create therapy recommendation record
            recommendation_record = self._create_recommendation_record(user, analysis)

            # Generate insights if needed
            self._check_for_urgent_insights(user, analysis)

            # Prepare final response
            result = self._format_therapy_analysis_response(
                analysis, recommendation_record
            )

            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)

            return result

        except Exception as e:
            logger.error(f"Error in therapy session analysis: {str(e)}", exc_info=True)
            return self._create_error_response(str(e))

    def _collect_comprehensive_data(self, user, days: int) -> Dict[str, Any]:
        """Collect all relevant data for therapy analysis"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Import here to avoid circular imports
            from mood.models import MoodLog
            from journal.models import JournalEntry

            # Get mood data
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            mood_data = [
                {
                    "rating": log.mood_rating,
                    "timestamp": log.logged_at.isoformat(),
                    "activities": getattr(log, "activities", []),
                    "notes": getattr(log, "notes", ""),
                    "day_of_week": log.logged_at.strftime("%A"),
                    "hour": log.logged_at.hour,
                }
                for log in mood_logs
            ]

            # Get journal data
            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("created_at")

            journal_data = [
                {
                    "content": entry.content,
                    "mood": entry.mood,
                    "timestamp": entry.created_at.isoformat(),
                    "activities": getattr(entry, "activities", []),
                    "category": getattr(entry.category, "name", "general")
                    if hasattr(entry, "category") and entry.category
                    else "general",
                    "content_length": len(entry.content),
                    "emotional_indicators": self._extract_emotional_indicators(
                        entry.content
                    ),
                }
                for entry in journal_entries
            ]

            # Get previous therapy recommendations for context
            previous_recommendations = self._get_previous_recommendations(user, days=30)

            # Calculate trend analysis
            trend_analysis = self._calculate_trend_analysis(mood_data, journal_data)

            # Get contextual factors
            contextual_factors = self._get_contextual_factors(
                user, start_date, end_date
            )

            return {
                "mood_data": mood_data,
                "journal_data": journal_data,
                "previous_recommendations": previous_recommendations,
                "trend_analysis": trend_analysis,
                "contextual_factors": contextual_factors,
                "analysis_period_days": days,
                "data_collection_date": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error collecting comprehensive data: {str(e)}")
            return {"error": str(e), "mood_data": [], "journal_data": []}

    def _extract_emotional_indicators(self, content: str) -> Dict[str, int]:
        """Extract emotional indicators from text content"""
        try:
            content_lower = content.lower()

            emotional_patterns = {
                "anxiety_indicators": [
                    r"\banxious\b",
                    r"\bworried\b",
                    r"\bstressed\b",
                    r"\bnervous\b",
                    r"\bpanic\b",
                ],
                "depression_indicators": [
                    r"\bsad\b",
                    r"\bdepressed\b",
                    r"\bhopeless\b",
                    r"\bempty\b",
                    r"\bworthless\b",
                ],
                "anger_indicators": [
                    r"\bangry\b",
                    r"\bfrustrated\b",
                    r"\birritated\b",
                    r"\bmad\b",
                    r"\bfurious\b",
                ],
                "positive_indicators": [
                    r"\bhappy\b",
                    r"\bjoyful\b",
                    r"\bexcited\b",
                    r"\bproud\b",
                    r"\bgrateful\b",
                ],
                "coping_indicators": [
                    r"\bbreathing\b",
                    r"\bmeditation\b",
                    r"\bexercise\b",
                    r"\btalk\b",
                    r"\bhelp\b",
                ],
            }

            indicators = {}
            for category, patterns in emotional_patterns.items():
                count = sum(
                    len(re.findall(pattern, content_lower)) for pattern in patterns
                )
                indicators[category] = count

            return indicators

        except Exception as e:
            logger.error(f"Error extracting emotional indicators: {str(e)}")
            return {}

    def _get_previous_recommendations(self, user, days: int = 30) -> List[Dict]:
        """Get previous therapy recommendations for context"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)

            previous_recs = TherapyRecommendation.objects.filter(
                user=user, created_at__gte=cutoff_date
            ).order_by("-created_at")[:5]  # Last 5 recommendations

            return [
                {
                    "recommendation_type": rec.recommendation_type,
                    "recommendation_data": rec.recommendation_data,
                    "is_implemented": rec.is_implemented,
                    "effectiveness_rating": rec.effectiveness_rating,
                    "created_at": rec.created_at.isoformat(),
                }
                for rec in previous_recs
            ]

        except Exception as e:
            logger.error(f"Error getting previous recommendations: {str(e)}")
            return []

    def _calculate_trend_analysis(
        self, mood_data: List[Dict], journal_data: List[Dict]
    ) -> Dict:
        """Calculate trend analysis for therapy insights"""
        try:
            if not mood_data:
                return {
                    "mood_trend": "insufficient_data",
                    "journal_trend": "insufficient_data",
                }

            # Mood trend analysis
            mood_ratings = [entry["rating"] for entry in mood_data]
            mood_trend = self._calculate_linear_trend(mood_ratings)

            # Journal sentiment trend
            journal_sentiment_trend = "stable"
            if journal_data:
                # Simple sentiment analysis based on mood field
                recent_moods = [
                    entry["mood"] for entry in journal_data[-5:] if entry.get("mood")
                ]
                if recent_moods:
                    positive_count = sum(
                        1
                        for mood in recent_moods
                        if mood in ["positive", "very_positive"]
                    )
                    negative_count = sum(
                        1
                        for mood in recent_moods
                        if mood in ["negative", "very_negative"]
                    )

                    if positive_count > negative_count:
                        journal_sentiment_trend = "improving"
                    elif negative_count > positive_count:
                        journal_sentiment_trend = "declining"

            # Activity patterns
            activity_patterns = self._analyze_activity_patterns(mood_data)

            return {
                "mood_trend": mood_trend,
                "mood_average": np.mean(mood_ratings) if mood_ratings else 0,
                "mood_volatility": np.std(mood_ratings) if len(mood_ratings) > 1 else 0,
                "journal_sentiment_trend": journal_sentiment_trend,
                "activity_patterns": activity_patterns,
                "data_consistency": len(mood_data) / 7
                if len(mood_data) <= 7
                else 1.0,  # Ratio of actual to expected data points
            }

        except Exception as e:
            logger.error(f"Error in trend analysis: {str(e)}")
            return {"error": str(e)}

    def _calculate_linear_trend(self, values: List[float]) -> str:
        """Calculate linear trend from a list of values"""
        try:
            if len(values) < 2:
                return "insufficient_data"

            x = np.arange(len(values))
            slope = np.polyfit(x, values, 1)[0]

            if slope > 0.1:
                return "improving"
            elif slope < -0.1:
                return "declining"
            else:
                return "stable"

        except Exception:
            return "unknown"

    def _analyze_activity_patterns(self, mood_data: List[Dict]) -> Dict:
        """Analyze patterns in activities and their correlation with mood"""
        try:
            activity_mood_map = {}

            for entry in mood_data:
                activities = entry.get("activities", [])
                mood = entry.get("rating", 5)

                for activity in activities:
                    if activity not in activity_mood_map:
                        activity_mood_map[activity] = []
                    activity_mood_map[activity].append(mood)

            # Calculate average mood for each activity
            activity_analysis = {}
            for activity, moods in activity_mood_map.items():
                if len(moods) > 0:  # Ensure we have mood data
                    activity_analysis[activity] = {
                        "average_mood": float(np.mean(moods)),
                        "frequency": len(moods),
                        "mood_range": float(max(moods) - min(moods)) if len(moods) > 1 else 0,
                        "positive_correlation": float(np.mean(moods)) > 6.0,  # Above neutral
                    }

            return activity_analysis

        except Exception as e:
            logger.error(f"Error analyzing activity patterns: {str(e)}")
            return {}

    def _get_contextual_factors(self, user, start_date, end_date) -> Dict:
        """Get contextual factors that might influence therapy"""
        try:
            contextual_data = {
                "time_period": f"{start_date.date()} to {end_date.date()}",
                "season": self._get_season(end_date),
                "recent_events": [],
                "medication_mentions": 0,
                "sleep_mentions": 0,
                "social_mentions": 0,
            }

            # Try to get additional context from journal entries
            try:
                from journal.models import JournalEntry

                recent_entries = JournalEntry.objects.filter(
                    user=user, created_at__range=(start_date, end_date)
                )

                all_content = " ".join(
                    [entry.content.lower() for entry in recent_entries]
                )

                # Count mentions of important topics
                contextual_data["medication_mentions"] = len(
                    re.findall(r"\b(medication|pill|dose|medicine)\b", all_content)
                )
                contextual_data["sleep_mentions"] = len(
                    re.findall(r"\b(sleep|tired|insomnia|rest)\b", all_content)
                )
                contextual_data["social_mentions"] = len(
                    re.findall(r"\b(friend|family|social|alone|lonely)\b", all_content)
                )

            except Exception as e:
                logger.error(f"Error getting journal context: {str(e)}")

            return contextual_data

        except Exception as e:
            logger.error(f"Error getting contextual factors: {str(e)}")
            return {}

    def _get_season(self, date) -> str:
        """Determine the season for seasonal context"""
        month = date.month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def _has_sufficient_data(self, data: Dict) -> bool:
        """Check if there's sufficient data for meaningful analysis"""
        mood_count = len(data.get("mood_data", []))
        journal_count = len(data.get("journal_data", []))

        # Need at least some data points for analysis
        return mood_count >= 2 or journal_count >= 1

    def _analyze_with_ollama(self, data: Dict) -> Dict[str, Any]:
        """Analyze data using Ollama for therapy recommendations"""
        try:
            prompt = self._build_therapy_analysis_prompt(data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "{}")

                try:
                    # Try to extract JSON from response
                    if "```json" in response_text:
                        json_start = response_text.find("```json") + 7
                        json_end = response_text.find("```", json_start)
                        json_str = response_text[json_start:json_end].strip()
                        analysis = json.loads(json_str)
                    elif "```" in response_text and response_text.count("```") >= 2:
                        json_start = response_text.find("```") + 3
                        json_end = response_text.find("```", json_start)
                        json_str = response_text[json_start:json_end].strip()
                        analysis = json.loads(json_str)
                    else:
                        # Try to parse the entire response as JSON
                        analysis = json.loads(response_text)

                    # Validate and enhance the analysis
                    return self._validate_and_enhance_analysis(analysis)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Response text: {response_text[:500]}...")
                    return self._create_fallback_analysis(data)

            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                return self._create_fallback_analysis(data)

        except Exception as e:
            logger.error(f"Error in Ollama analysis: {str(e)}")
            return self._create_fallback_analysis(data)

    def _build_therapy_analysis_prompt(self, data: Dict) -> str:
        """Build comprehensive prompt for therapy analysis"""
        mood_summary = self._summarize_mood_data(data.get("mood_data", []))
        journal_summary = self._summarize_journal_data(data.get("journal_data", []))
        trend_summary = data.get("trend_analysis", {})

        prompt = f"""As a mental health professional, analyze this patient data and recommend therapy session focus areas:

MOOD DATA SUMMARY:
{mood_summary}

JOURNAL ENTRIES SUMMARY:
{journal_summary}

TREND ANALYSIS:
- Mood trend: {trend_summary.get('mood_trend', 'unknown')}
- Average mood: {trend_summary.get('mood_average', 0):.1f}/10
- Mood volatility: {trend_summary.get('mood_volatility', 0):.1f}
- Journal sentiment: {trend_summary.get('journal_sentiment_trend', 'unknown')}

CONTEXTUAL FACTORS:
{data.get('contextual_factors', {})}

PREVIOUS RECOMMENDATIONS:
{len(data.get('previous_recommendations', []))} previous recommendations available

Provide recommendations in JSON format:
{{
    "focus_areas": [<list of main areas to focus on in therapy>],
    "session_goals": [<list of specific goals for next session>],
    "therapeutic_approaches": [<list of recommended therapeutic approaches (CBT, DBT, etc.)>],
    "priority_issues": [<list of urgent issues to address>],
    "progress_notes": "<summary of patient's current progress>",
    "intervention_suggestions": [<specific interventions to try>],
    "homework_assignments": [<therapeutic homework suggestions>],
    "risk_assessment": {{
        "risk_level": "<low|medium|high>",
        "risk_factors": [<identified risk factors>],
        "protective_factors": [<identified protective factors>]
    }},
    "treatment_plan_updates": [<suggestions for treatment plan modifications>],
    "next_session_timing": "<recommended timing for next session>",
    "requires_immediate_attention": <boolean>,
    "therapist_notes": "<important notes for the therapist>"
}}"""

        # Ensure prompt isn't too long
        if len(prompt) > self.max_prompt_length:
            prompt = (
                prompt[: self.max_prompt_length - 200]
                + "\n\nProvide the JSON analysis based on available data."
            )

        return prompt

    def _summarize_mood_data(self, mood_data: List[Dict]) -> str:
        """Create a summary of mood data for the prompt"""
        if not mood_data:
            return "No mood data available for this period."

        ratings = [entry["rating"] for entry in mood_data]
        avg_mood = np.mean(ratings)
        mood_range = f"{min(ratings)}-{max(ratings)}" if ratings else "N/A"

        recent_entries = mood_data[-3:] if len(mood_data) >= 3 else mood_data

        return f"""
- Total mood logs: {len(mood_data)}
- Average mood: {avg_mood:.1f}/10
- Mood range: {mood_range}
- Recent entries: {[entry['rating'] for entry in recent_entries]}
- Most common activities: {self._get_common_activities(mood_data)}
"""

    def _summarize_journal_data(self, journal_data: List[Dict]) -> str:
        """Create a summary of journal data for the prompt"""
        if not journal_data:
            return "No journal entries available for this period."

        total_entries = len(journal_data)
        avg_length = np.mean([entry.get("content_length", 0) for entry in journal_data])

        # Get sample of recent content (first 100 chars of each)
        recent_content_samples = [
            entry["content"][:100] + "..."
            if len(entry["content"]) > 100
            else entry["content"]
            for entry in journal_data[-3:]
        ]

        return f"""
- Total journal entries: {total_entries}
- Average entry length: {avg_length:.0f} characters
- Recent entries sample: {recent_content_samples}
"""

    def _get_common_activities(self, mood_data: List[Dict]) -> List[str]:
        """Get most common activities from mood data"""
        try:
            activity_counts = {}
            for entry in mood_data:
                for activity in entry.get("activities", []):
                    activity_counts[activity] = activity_counts.get(activity, 0) + 1

            # Return top 3 most common activities
            sorted_activities = sorted(
                activity_counts.items(), key=lambda x: x[1], reverse=True
            )
            return [activity for activity, count in sorted_activities[:3]]

        except Exception:
            return []

    def _validate_and_enhance_analysis(self, analysis: Dict) -> Dict:
        """Validate and enhance the AI analysis response"""
        required_fields = {
            "focus_areas": [],
            "session_goals": [],
            "therapeutic_approaches": [],
            "priority_issues": [],
            "progress_notes": "",
            "intervention_suggestions": [],
            "homework_assignments": [],
            "risk_assessment": {
                "risk_level": "medium",
                "risk_factors": [],
                "protective_factors": [],
            },
            "treatment_plan_updates": [],
            "next_session_timing": "1 week",
            "requires_immediate_attention": False,
            "therapist_notes": "",
        }

        # Ensure all required fields exist
        for field, default_value in required_fields.items():
            if field not in analysis:
                analysis[field] = default_value

        # Validate risk assessment structure
        if not isinstance(analysis["risk_assessment"], dict):
            analysis["risk_assessment"] = required_fields["risk_assessment"]

        # Add confidence score based on completeness
        completeness = sum(1 for field in required_fields if analysis.get(field))
        analysis["analysis_confidence"] = completeness / len(required_fields)

        return analysis

    def _create_fallback_analysis(self, data: Dict) -> Dict:
        """Create fallback analysis when AI analysis fails"""
        mood_data = data.get("mood_data", [])
        journal_data = data.get("journal_data", [])
        trend_analysis = data.get("trend_analysis", {})

        # Basic analysis based on available data
        focus_areas = ["mood_monitoring", "coping_strategies"]
        session_goals = ["Review recent mood patterns", "Discuss coping mechanisms"]

        # Adjust based on trends
        if trend_analysis.get("mood_trend") == "declining":
            focus_areas.append("crisis_prevention")
            session_goals.append("Identify triggers for mood decline")

        if len(journal_data) > 0:
            focus_areas.append("journaling_review")
            session_goals.append("Process journal insights")

        return {
            "focus_areas": focus_areas,
            "session_goals": session_goals,
            "therapeutic_approaches": ["CBT", "supportive_therapy"],
            "priority_issues": ["mood_stability"]
            if trend_analysis.get("mood_trend") == "declining"
            else [],
            "progress_notes": f"Patient has logged {len(mood_data)} mood entries and {len(journal_data)} journal entries in the analysis period.",
            "intervention_suggestions": ["mood_tracking", "relaxation_techniques"],
            "homework_assignments": [
                "Continue mood logging",
                "Practice deep breathing exercises",
            ],
            "risk_assessment": {
                "risk_level": "medium"
                if trend_analysis.get("mood_trend") == "declining"
                else "low",
                "risk_factors": ["declining_mood_trend"]
                if trend_analysis.get("mood_trend") == "declining"
                else [],
                "protective_factors": ["regular_app_usage", "self_monitoring"],
            },
            "treatment_plan_updates": ["Consider increasing session frequency"]
            if trend_analysis.get("mood_trend") == "declining"
            else [],
            "next_session_timing": "1 week",
            "requires_immediate_attention": False,
            "therapist_notes": "Analysis generated using fallback method due to AI processing limitations.",
            "analysis_confidence": 0.6,
            "is_fallback": True,
        }

    def _create_recommendation_record(self, user, analysis: Dict) -> Optional[object]:
        """Create a therapy recommendation record"""
        try:
            recommendation = TherapyRecommendation.objects.create(
                user=user,
                recommendation_type="session_preparation",
                recommendation_data={
                    "focus_areas": analysis.get("focus_areas", []),
                    "session_goals": analysis.get("session_goals", []),
                    "therapeutic_approaches": analysis.get(
                        "therapeutic_approaches", []
                    ),
                    "intervention_suggestions": analysis.get(
                        "intervention_suggestions", []
                    ),
                    "homework_assignments": analysis.get("homework_assignments", []),
                    "next_session_timing": analysis.get(
                        "next_session_timing", "1 week"
                    ),
                    "analysis_confidence": analysis.get("analysis_confidence", 0.5),
                },
                context_data={
                    "risk_assessment": analysis.get("risk_assessment", {}),
                    "progress_notes": analysis.get("progress_notes", ""),
                    "therapist_notes": analysis.get("therapist_notes", ""),
                    "requires_immediate_attention": analysis.get(
                        "requires_immediate_attention", False
                    ),
                },
            )

            logger.info(
                f"Created therapy recommendation record {recommendation.id} for user {user.id}"
            )
            return recommendation

        except Exception as e:
            logger.error(f"Error creating recommendation record: {str(e)}")
            return None

    def _check_for_urgent_insights(self, user, analysis: Dict):
        """Check for urgent patterns and create insights if needed"""
        try:
            risk_assessment = analysis.get("risk_assessment", {})

            if (
                analysis.get("requires_immediate_attention")
                or risk_assessment.get("risk_level") == "high"
            ):
                AIInsight.objects.create(
                    user=user,
                    insight_type="therapy_urgent",
                    insight_data={
                        "urgency_reason": "high_risk_therapy_analysis",
                        "risk_level": risk_assessment.get("risk_level", "high"),
                        "risk_factors": risk_assessment.get("risk_factors", []),
                        "priority_issues": analysis.get("priority_issues", []),
                        "immediate_actions": analysis.get(
                            "intervention_suggestions", []
                        ),
                    },
                    priority="high",
                )

                logger.warning(f"Created urgent therapy insight for user {user.id}")

        except Exception as e:
            logger.error(f"Error checking for urgent insights: {str(e)}")

    def _format_therapy_analysis_response(
        self, analysis: Dict, recommendation_record
    ) -> Dict:
        """Format the final therapy analysis response"""
        return {
            "success": True,
            "recommendation_id": recommendation_record.id
            if recommendation_record
            else None,
            "analysis": {
                "focus_areas": analysis.get("focus_areas", []),
                "session_goals": analysis.get("session_goals", []),
                "therapeutic_approaches": analysis.get("therapeutic_approaches", []),
                "priority_issues": analysis.get("priority_issues", []),
                "intervention_suggestions": analysis.get(
                    "intervention_suggestions", []
                ),
                "homework_assignments": analysis.get("homework_assignments", []),
                "progress_notes": analysis.get("progress_notes", ""),
                "next_session_timing": analysis.get("next_session_timing", "1 week"),
                "requires_immediate_attention": analysis.get(
                    "requires_immediate_attention", False
                ),
                "analysis_confidence": analysis.get("analysis_confidence", 0.5),
            },
            "risk_assessment": analysis.get("risk_assessment", {}),
            "therapist_notes": analysis.get("therapist_notes", ""),
            "treatment_plan_updates": analysis.get("treatment_plan_updates", []),
            "timestamp": timezone.now().isoformat(),
            "is_fallback": analysis.get("is_fallback", False),
        }

    def _create_insufficient_data_response(self, data: Dict) -> Dict:
        """Create response when there's insufficient data"""
        return {
            "success": False,
            "reason": "insufficient_data",
            "message": "Not enough mood or journal data to generate meaningful therapy recommendations",
            "data_summary": {
                "mood_entries": len(data.get("mood_data", [])),
                "journal_entries": len(data.get("journal_data", [])),
                "minimum_required": "At least 2 mood entries or 1 journal entry",
            },
            "suggestions": [
                "Encourage patient to log mood more regularly",
                "Suggest journaling as a therapeutic tool",
                "Consider using previous session notes for context",
            ],
        }

    def _create_error_response(self, error_message: str) -> Dict:
        """Create error response"""
        return {
            "success": False,
            "reason": "analysis_error",
            "message": f"Error during therapy analysis: {error_message}",
            "fallback_recommendations": [
                "Review patient's recent mood patterns manually",
                "Focus on established therapeutic goals",
                "Use clinical judgment for session planning",
            ],
        }

    def _create_default_analysis(self) -> Dict:
        """Create default analysis for fallback scenarios"""
        return {
            "focus_areas": ["general_wellbeing", "coping_strategies"],
            "session_goals": ["Check in on overall mood", "Review coping mechanisms"],
            "therapeutic_approaches": ["supportive_therapy"],
            "priority_issues": [],
            "progress_notes": "Standard check-in session recommended",
            "intervention_suggestions": ["mood_monitoring"],
            "homework_assignments": ["Continue self-care practices"],
            "risk_assessment": {
                "risk_level": "low",
                "risk_factors": [],
                "protective_factors": ["regular_therapy_attendance"],
            },
            "treatment_plan_updates": [],
            "next_session_timing": "1 week",
            "requires_immediate_attention": False,
            "therapist_notes": "Default analysis due to service limitations",
            "analysis_confidence": 0.3,
        }

    def get_therapy_insights_for_chatbot(self, user, limit: int = 3) -> List[Dict]:
        """Get therapy insights for chatbot context"""
        try:
            recent_recommendations = TherapyRecommendation.objects.filter(
                user=user
            ).order_by("-created_at")[:limit]

            insights = []
            for rec in recent_recommendations:
                insights.append(
                    {
                        "type": "therapy_recommendation",
                        "focus_areas": rec.recommendation_data.get("focus_areas", []),
                        "therapeutic_approaches": rec.recommendation_data.get(
                            "therapeutic_approaches", []
                        ),
                        "current_goals": rec.recommendation_data.get(
                            "session_goals", []
                        ),
                        "created_at": rec.created_at.isoformat(),
                        "is_implemented": rec.is_implemented,
                    }
                )

            return insights

        except Exception as e:
            logger.error(f"Error getting therapy insights for chatbot: {str(e)}")
            return []


# Create singleton instance
therapy_analysis_service = TherapyAnalysisService()

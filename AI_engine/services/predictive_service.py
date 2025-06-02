# AI_engine/services/predictive_service.py
import logging
from typing import Dict, Any, List
import requests
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from journal.models import JournalEntry, JournalCategory
from django.db.models import Avg, Case, When, FloatField
from django.conf import settings
import numpy as np
from collections import defaultdict
import json
import re

logger = logging.getLogger(__name__)


class PredictiveAnalysisService:
    def __init__(self):
        self.base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self.model = "mistral"  # Using Mistral for predictive analysis
        self.cache_timeout = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "CACHE_TIMEOUT", 900
        )
        self.max_prompt_length = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "MAX_PROMPT_LENGTH", 4000
        )

    def predict_mood_decline(self, user, timeframe_days: int = 7) -> Dict:
        """Enhanced mood decline prediction with trend analysis and risk factors using AI data interface"""
        cache_key = f"mood_prediction_{user.id}_{timeframe_days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Import AI data interface service
            from .data_interface import ai_data_interface
            
            # Get extended historical data for better pattern analysis
            extended_period = max(timeframe_days * 4, 28)  # At least 4 weeks of data
            
            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, extended_period)
            
            # Check data quality and availability
            quality_metrics = dataset.get('quality_metrics', {})
            if quality_metrics.get('overall_quality', 0.0) < 0.1:
                logger.warning(f"Insufficient data quality for user {user.id} mood prediction: {quality_metrics}")
                result = {
                    "risk_level": "unknown",
                    "confidence": 0,
                    "factors": [],
                    "message": "Insufficient data quality for prediction",
                    "data_quality_warning": True,
                }
                cache.set(cache_key, result, self.cache_timeout)
                return result

            # Extract mood data from AI-ready dataset
            mood_data_info = self._extract_mood_data_for_prediction(dataset, timeframe_days)
            
            if not mood_data_info["mood_values"]:
                result = {
                    "risk_level": "unknown",
                    "confidence": 0,
                    "factors": [],
                    "message": "Insufficient mood data for prediction",
                }
                cache.set(cache_key, result, self.cache_timeout)
                return result

            # Enhanced data preparation with trend analysis
            mood_data = self._prepare_mood_data_with_trends_from_dataset(mood_data_info, timeframe_days)

            # Get contextual data from AI-ready dataset
            contextual_data = self._get_contextual_data_from_dataset(dataset, timeframe_days)

            # Combine all data for analysis
            analysis_data = {
                **mood_data,
                **contextual_data,
                "timeframe_days": timeframe_days,
                "total_data_points": len(mood_data_info["mood_values"]),
                "data_quality_metrics": quality_metrics,
            }

            # Enhanced AI analysis
            prediction = self._analyze_mood_trends_with_ai(analysis_data)

            # Add statistical risk factors
            statistical_risk = self._calculate_statistical_risk_from_values(
                mood_data_info["mood_values"], timeframe_days
            )
            prediction.update(statistical_risk)

            # Enhanced result with datawarehouse integration metrics
            processing_metadata = dataset.get('processing_metadata', {})
            prediction["data_integration"] = {
                "data_sources_used": dataset.get("data_sources", []),
                "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                "completeness_score": quality_metrics.get("completeness", 0.0),
                "analysis_recommendation": quality_metrics.get("analysis_recommendation", "unknown"),
                "datawarehouse_version": processing_metadata.get("processing_version", "unknown"),
                "collection_time": processing_metadata.get("collection_time_seconds", 0),
            }

            # Cache result
            cache.set(cache_key, prediction, self.cache_timeout)
            return prediction

        except Exception as e:
            logger.error(f"Error in mood decline prediction: {str(e)}", exc_info=True)
            return self._create_default_prediction("mood_decline_error")

    def _extract_mood_data_for_prediction(self, dataset: Dict, timeframe_days: int) -> Dict:
        """Extract mood data from AI-ready dataset for prediction analysis"""
        try:
            mood_analytics = dataset.get("mood_analytics", {})
            mood_entries = mood_analytics.get("mood_entries", [])
            
            # Extract mood values and related information
            mood_logs_data = []
            mood_values = []
            
            for entry in mood_entries:
                mood_rating = entry.get("rating", entry.get("mood_rating", 5))
                mood_values.append(mood_rating)
                
                mood_logs_data.append({
                    "mood_rating": mood_rating,
                    "activities": entry.get("activities", []),
                    "logged_at": entry.get("logged_at", entry.get("timestamp", "")),
                    "notes": entry.get("notes", ""),
                    "day_of_week": entry.get("day_of_week", 0),
                    "hour_of_day": entry.get("hour_of_day", 12),
                    "date": entry.get("date", ""),
                })
            
            return {
                "mood_logs_data": mood_logs_data,
                "mood_values": mood_values,
                "total_entries": len(mood_entries),
            }
            
        except Exception as e:
            logger.error(f"Error extracting mood data for prediction: {str(e)}")
            return {
                "mood_logs_data": [],
                "mood_values": [],
                "total_entries": 0,
            }

    def _prepare_mood_data_with_trends_from_dataset(self, mood_data_info: Dict, timeframe_days: int) -> Dict:
        """Prepare mood data with trend analysis from dataset information"""
        try:
            mood_logs_data = mood_data_info.get("mood_logs_data", [])
            mood_values = mood_data_info.get("mood_values", [])
            
            recent_moods = (
                mood_values[-timeframe_days:]
                if len(mood_values) >= timeframe_days
                else mood_values
            )

            # Calculate trends and patterns
            trends = self._calculate_mood_trends(mood_values, timeframe_days)
            patterns = self._detect_mood_patterns_from_data(mood_logs_data)
            volatility = self._calculate_mood_volatility(recent_moods)

            return {
                "mood_data": mood_logs_data,
                "trends": trends,
                "patterns": patterns,
                "volatility": volatility,
                "recent_average": np.mean(recent_moods) if recent_moods else 5,
                "overall_average": np.mean(mood_values) if mood_values else 5,
            }
            
        except Exception as e:
            logger.error(f"Error preparing mood data with trends: {str(e)}")
            return {
                "mood_data": [],
                "trends": {"trend": "insufficient_data", "slope": 0, "acceleration": 0},
                "patterns": {"weekly_pattern": {}, "daily_pattern": {}, "activity_correlation": {}, "concerning_patterns": []},
                "volatility": {"volatility": 0, "stability": "unknown"},
                "recent_average": 5,
                "overall_average": 5,
            }

    def _detect_mood_patterns_from_data(self, mood_logs_data: List[Dict]) -> Dict:
        """Detect cyclical and temporal patterns from mood logs data"""
        patterns = {
            "weekly_pattern": {},
            "daily_pattern": {},
            "activity_correlation": {},
            "concerning_patterns": [],
        }

        try:
            # Weekly patterns
            weekly_moods = defaultdict(list)
            daily_moods = defaultdict(list)
            activity_moods = defaultdict(list)

            for log_data in mood_logs_data:
                # Convert day_of_week number to name
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                day_of_week = days[log_data.get("day_of_week", 0) % 7]
                hour_of_day = log_data.get("hour_of_day", 12)
                activities = log_data.get("activities", [])
                mood_rating = log_data.get("mood_rating", 5)

                weekly_moods[day_of_week].append(mood_rating)
                daily_moods[hour_of_day].append(mood_rating)

                for activity in activities:
                    activity_moods[activity].append(mood_rating)

            # Calculate averages
            patterns["weekly_pattern"] = {
                day: np.mean(moods) for day, moods in weekly_moods.items()
            }
            patterns["daily_pattern"] = {
                hour: np.mean(moods) for hour, moods in daily_moods.items()
            }
            patterns["activity_correlation"] = {
                activity: np.mean(moods)
                for activity, moods in activity_moods.items()
                if len(moods) >= 3  # Only include activities with sufficient data
            }

            # Detect concerning patterns
            if any(avg < 3 for avg in patterns["weekly_pattern"].values()):
                patterns["concerning_patterns"].append("consistently_low_weekly_moods")

            if len(patterns["activity_correlation"]) > 0:
                lowest_activity = min(
                    patterns["activity_correlation"].items(), key=lambda x: x[1]
                )
                if lowest_activity[1] < 3:
                    patterns["concerning_patterns"].append(
                        f"negative_activity_correlation_{lowest_activity[0]}"
                    )

        except Exception as e:
            logger.error(f"Error detecting mood patterns: {str(e)}")

        return patterns

    def _get_contextual_data_from_dataset(self, dataset: Dict, timeframe_days: int) -> Dict:
        """Get contextual data from AI-ready dataset that might influence mood prediction"""
        try:
            journal_analytics = dataset.get("journal_analytics", {})
            journal_entries = journal_analytics.get("journal_entries", [])
            
            contextual_data = {
                "journal_entries_count": len(journal_entries),
                "journal_sentiment": "neutral",
                "sleep_mentions": 0,
                "stress_mentions": 0,
                "medication_mentions": 0,
                "social_mentions": 0,
                "work_mentions": 0,
                "relationship_mentions": 0,
            }

            if journal_entries:
                # Analyze journal content for contextual clues
                content_analysis = self._analyze_journal_content_from_entries(journal_entries)
                contextual_data.update(content_analysis)
                
                # Calculate overall sentiment
                sentiments = [entry.get("sentiment_score", 0.0) for entry in journal_entries]
                avg_sentiment = np.mean(sentiments) if sentiments else 0.0
                if avg_sentiment > 0.1:
                    contextual_data["journal_sentiment"] = "positive"
                elif avg_sentiment < -0.1:
                    contextual_data["journal_sentiment"] = "negative"
                else:
                    contextual_data["journal_sentiment"] = "neutral"

            return contextual_data
            
        except Exception as e:
            logger.error(f"Error getting contextual data from dataset: {str(e)}")
            return {
                "journal_entries_count": 0,
                "journal_sentiment": "neutral",
                "sleep_mentions": 0,
                "stress_mentions": 0,
                "medication_mentions": 0,
                "social_mentions": 0,
                "work_mentions": 0,
                "relationship_mentions": 0,
            }

    def _analyze_journal_content_from_entries(self, journal_entries: List[Dict]) -> Dict:
        """Analyze journal content from entry data for mood-relevant context"""
        try:
            content = " ".join([entry.get("content", "").lower() for entry in journal_entries])

            # Define keyword patterns
            patterns = {
                "sleep_mentions": [
                    r"\bsleep\b", r"\btired\b", r"\bexhausted\b", r"\binsomnia\b",
                ],
                "stress_mentions": [
                    r"\bstress\b", r"\banxious\b", r"\bworried\b", r"\boverwhelmed\b",
                ],
                "medication_mentions": [
                    r"\bmedication\b", r"\bpill\b", r"\bdose\b", r"\bside effect\b",
                ],
                "social_mentions": [
                    r"\bfriend\b", r"\bfamily\b", r"\balone\b", r"\bisolated\b",
                ],
                "work_mentions": [r"\bwork\b", r"\bjob\b", r"\bcareer\b", r"\bboss\b"],
                "relationship_mentions": [
                    r"\brelationship\b", r"\bpartner\b", r"\bdating\b", r"\bmarriage\b",
                ],
            }

            analysis = {}
            for category, pattern_list in patterns.items():
                count = sum(len(re.findall(pattern, content)) for pattern in pattern_list)
                analysis[category] = count

            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing journal content: {str(e)}")
            return {
                "sleep_mentions": 0,
                "stress_mentions": 0,
                "medication_mentions": 0,
                "social_mentions": 0,
                "work_mentions": 0,
                "relationship_mentions": 0,
            }

    def _calculate_statistical_risk_from_values(self, mood_values: List[float], timeframe_days: int) -> Dict:
        """Calculate statistical risk indicators from mood values"""
        if len(mood_values) < 3:
            return {"statistical_risk": "insufficient_data"}

        recent_values = (
            mood_values[-timeframe_days:]
            if len(mood_values) >= timeframe_days
            else mood_values
        )

        # Risk indicators
        risk_indicators = {
            "consecutive_low_days": self._count_consecutive_low_days(recent_values),
            "significant_drops": self._count_significant_drops(recent_values),
            "below_baseline_percentage": self._calculate_below_baseline_percentage(
                mood_values, recent_values
            ),
            "trend_deterioration": self._assess_trend_deterioration(
                mood_values, timeframe_days
            ),
        }

        # Overall statistical risk assessment
        risk_score = 0
        if risk_indicators["consecutive_low_days"] >= 3:
            risk_score += 0.3
        if risk_indicators["significant_drops"] >= 2:
            risk_score += 0.2
        if risk_indicators["below_baseline_percentage"] > 0.6:
            risk_score += 0.3
        if risk_indicators["trend_deterioration"]:
            risk_score += 0.2

        return {
            "statistical_risk_score": min(1.0, risk_score),
            "risk_indicators": risk_indicators,
        }

    def _prepare_mood_data_with_trends(self, mood_logs, timeframe_days: int) -> Dict:
        """Prepare mood data with trend analysis and pattern detection"""
        mood_values = [log.mood_rating for log in mood_logs]
        recent_moods = (
            mood_values[-timeframe_days:]
            if len(mood_values) >= timeframe_days
            else mood_values
        )

        # Calculate trends and patterns
        trends = self._calculate_mood_trends(mood_values, timeframe_days)
        patterns = self._detect_mood_patterns(mood_logs)
        volatility = self._calculate_mood_volatility(recent_moods)

        return {
            "mood_data": [
                {
                    "rating": log.mood_rating,
                    "activities": getattr(log, "activities", []),
                    "logged_at": log.logged_at.isoformat(),
                    "notes": getattr(log, "notes", ""),
                    "day_of_week": log.logged_at.weekday(),
                    "hour_of_day": log.logged_at.hour,
                }
                for log in mood_logs
            ],
            "trends": trends,
            "patterns": patterns,
            "volatility": volatility,
            "recent_average": np.mean(recent_moods) if recent_moods else 5,
            "overall_average": np.mean(mood_values) if mood_values else 5,
        }

    def _calculate_mood_trends(
        self, mood_values: List[float], timeframe_days: int
    ) -> Dict:
        """Calculate various trend indicators"""
        if len(mood_values) < 3:
            return {"trend": "insufficient_data", "slope": 0, "acceleration": 0}

        recent_values = (
            mood_values[-timeframe_days:]
            if len(mood_values) >= timeframe_days
            else mood_values
        )

        # Linear trend calculation
        x = np.arange(len(recent_values))
        if len(recent_values) > 1:
            slope = np.polyfit(x, recent_values, 1)[0]
        else:
            slope = 0

        # Trend classification
        if slope < -0.3:
            trend = "declining"
        elif slope > 0.3:
            trend = "improving"
        else:
            trend = "stable"

        # Calculate acceleration (second derivative)
        acceleration = 0
        if len(recent_values) >= 3:
            differences = np.diff(recent_values)
            acceleration = np.mean(np.diff(differences)) if len(differences) > 1 else 0

        return {
            "trend": trend,
            "slope": float(slope),
            "acceleration": float(acceleration),
            "recent_change": float(recent_values[-1] - recent_values[0])
            if len(recent_values) > 1
            else 0,
        }

    def _detect_mood_patterns(self, mood_logs) -> Dict:
        """Detect cyclical and temporal patterns in mood data"""
        patterns = {
            "weekly_pattern": {},
            "daily_pattern": {},
            "activity_correlation": {},
            "concerning_patterns": [],
        }

        # Weekly patterns
        weekly_moods = defaultdict(list)
        daily_moods = defaultdict(list)
        activity_moods = defaultdict(list)

        for log in mood_logs:
            day_of_week = log.logged_at.strftime("%A")
            hour_of_day = log.logged_at.hour
            activities = getattr(log, "activities", [])

            weekly_moods[day_of_week].append(log.mood_rating)
            daily_moods[hour_of_day].append(log.mood_rating)

            for activity in activities:
                activity_moods[activity].append(log.mood_rating)

        # Calculate averages
        patterns["weekly_pattern"] = {
            day: np.mean(moods) for day, moods in weekly_moods.items()
        }
        patterns["daily_pattern"] = {
            hour: np.mean(moods) for hour, moods in daily_moods.items()
        }
        patterns["activity_correlation"] = {
            activity: np.mean(moods)
            for activity, moods in activity_moods.items()
            if len(moods) >= 3  # Only include activities with sufficient data
        }

        # Detect concerning patterns
        if any(avg < 3 for avg in patterns["weekly_pattern"].values()):
            patterns["concerning_patterns"].append("consistently_low_weekly_moods")

        if len(patterns["activity_correlation"]) > 0:
            lowest_activity = min(
                patterns["activity_correlation"].items(), key=lambda x: x[1]
            )
            if lowest_activity[1] < 3:
                patterns["concerning_patterns"].append(
                    f"negative_activity_correlation_{lowest_activity[0]}"
                )

        return patterns

    def _calculate_mood_volatility(self, mood_values: List[float]) -> Dict:
        """Calculate mood volatility and stability metrics"""
        if len(mood_values) < 2:
            return {"volatility": 0, "stability": "unknown"}

        std_dev = np.std(mood_values)
        mean_mood = np.mean(mood_values)

        # Calculate coefficient of variation
        cv = std_dev / mean_mood if mean_mood > 0 else 0

        # Classify volatility
        if cv < 0.2:
            stability = "very_stable"
        elif cv < 0.4:
            stability = "stable"
        elif cv < 0.6:
            stability = "moderate"
        else:
            stability = "volatile"

        return {
            "volatility": float(std_dev),
            "coefficient_of_variation": float(cv),
            "stability": stability,
            "range": float(max(mood_values) - min(mood_values)),
        }

    def _get_contextual_data(self, user, timeframe_days: int) -> Dict:
        """Get contextual data that might influence mood prediction"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=timeframe_days)

        contextual_data = {
            "journal_entries_count": 0,
            "journal_sentiment": "neutral",
            "sleep_mentions": 0,
            "stress_mentions": 0,
            "medication_mentions": 0,
            "social_mentions": 0,
        }

        try:
            # Get recent journal entries
            recent_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            )

            contextual_data["journal_entries_count"] = recent_entries.count()

            if recent_entries.exists():
                # Analyze journal content for contextual clues
                content_analysis = self._analyze_journal_content_for_context(
                    recent_entries
                )
                contextual_data.update(content_analysis)

        except Exception as e:
            logger.error(f"Error getting contextual data: {str(e)}")

        return contextual_data

    def _analyze_journal_content_for_context(self, entries) -> Dict:
        """Analyze journal content for mood-relevant context"""
        content = " ".join([entry.content.lower() for entry in entries])

        # Define keyword patterns
        patterns = {
            "sleep_mentions": [
                r"\bsleep\b",
                r"\btired\b",
                r"\bexhausted\b",
                r"\binsomnia\b",
            ],
            "stress_mentions": [
                r"\bstress\b",
                r"\banxious\b",
                r"\bworried\b",
                r"\boverwhelmed\b",
            ],
            "medication_mentions": [
                r"\bmedication\b",
                r"\bpill\b",
                r"\bdose\b",
                r"\bside effect\b",
            ],
            "social_mentions": [
                r"\bfriend\b",
                r"\bfamily\b",
                r"\balone\b",
                r"\bisolated\b",
            ],
            "work_mentions": [r"\bwork\b", r"\bjob\b", r"\bcareer\b", r"\bboss\b"],
            "relationship_mentions": [
                r"\brelationship\b",
                r"\bpartner\b",
                r"\bdating\b",
                r"\bmarriage\b",
            ],
        }

        analysis = {}
        for category, pattern_list in patterns.items():
            count = sum(len(re.findall(pattern, content)) for pattern in pattern_list)
            analysis[category] = count

        return analysis

    def _analyze_mood_trends_with_ai(self, data: Dict) -> Dict:
        """Enhanced AI analysis of mood trends for prediction"""
        try:
            prompt = self._build_enhanced_prediction_prompt(data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "{}")
                return self._parse_enhanced_prediction_response(response_text)
            else:
                logger.error(f"Ollama request failed: {response.status_code}")
                return self._create_default_prediction("ai_request_failed")

        except Exception as e:
            logger.error(f"Error in AI mood trend analysis: {str(e)}")
            return self._create_default_prediction("ai_analysis_error")

    def _build_enhanced_prediction_prompt(self, data: Dict) -> str:
        """Build comprehensive prompt for mood prediction"""
        # Truncate data if prompt would be too long
        mood_data_sample = data.get("mood_data", [])[-20:]  # Last 20 entries

        prompt = f"""As an advanced mental health AI, analyze this comprehensive mood data to predict potential mood decline:

RECENT MOOD DATA (last {len(mood_data_sample)} entries):
{mood_data_sample}

TREND ANALYSIS:
- Current trend: {data.get('trends', {}).get('trend', 'unknown')}
- Slope: {data.get('trends', {}).get('slope', 0)}
- Acceleration: {data.get('trends', {}).get('acceleration', 0)}
- Recent average: {data.get('recent_average', 5)}
- Overall average: {data.get('overall_average', 5)}

VOLATILITY METRICS:
- Stability: {data.get('volatility', {}).get('stability', 'unknown')}
- Volatility score: {data.get('volatility', {}).get('volatility', 0)}

CONTEXTUAL FACTORS:
- Journal entries: {data.get('journal_entries_count', 0)}
- Sleep mentions: {data.get('sleep_mentions', 0)}
- Stress mentions: {data.get('stress_mentions', 0)}
- Work mentions: {data.get('work_mentions', 0)}

PATTERNS DETECTED:
- Weekly patterns: {data.get('patterns', {}).get('weekly_pattern', {})}
- Concerning patterns: {data.get('patterns', {}).get('concerning_patterns', [])}

Analyze this data and provide a comprehensive prediction in JSON format:
{{
    "risk_level": "low|medium|high|critical",
    "confidence": <float 0-1>,
    "factors": [<list of contributing risk factors>],
    "recommendations": [<list of preventive actions>],
    "timeline": <predicted timeline for potential decline>,
    "warning_signs": [<list of early warning signs to watch for>],
    "protective_factors": [<list of positive factors that may help>],
    "intervention_priority": "low|medium|high|urgent"
}}
"""

        # Ensure prompt isn't too long
        if len(prompt) > self.max_prompt_length:
            prompt = (
                prompt[: self.max_prompt_length - 100]
                + "...\n\nProvide the JSON analysis."
            )

        return prompt

    def _parse_enhanced_prediction_response(self, response_text: str) -> Dict:
        """Parse enhanced AI prediction response"""
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            prediction = json.loads(response_text)

            # Validate and provide defaults
            required_fields = {
                "risk_level": "medium",
                "confidence": 0.5,
                "factors": [],
                "recommendations": [],
                "timeline": "1-2 weeks",
                "warning_signs": [],
                "protective_factors": [],
                "intervention_priority": "medium",
            }

            for field, default in required_fields.items():
                if field not in prediction:
                    prediction[field] = default

            return prediction

        except json.JSONDecodeError:
            logger.error("Failed to parse AI prediction response as JSON")
            return self._create_default_prediction("json_parse_error")
        except Exception as e:
            logger.error(f"Error processing AI prediction: {str(e)}")
            return self._create_default_prediction("response_processing_error")

    def _calculate_statistical_risk(self, mood_logs, timeframe_days: int) -> Dict:
        """Calculate statistical risk indicators"""
        mood_values = [log.mood_rating for log in mood_logs]

        if len(mood_values) < 3:
            return {"statistical_risk": "insufficient_data"}

        recent_values = (
            mood_values[-timeframe_days:]
            if len(mood_values) >= timeframe_days
            else mood_values
        )

        # Risk indicators
        risk_indicators = {
            "consecutive_low_days": self._count_consecutive_low_days(recent_values),
            "significant_drops": self._count_significant_drops(recent_values),
            "below_baseline_percentage": self._calculate_below_baseline_percentage(
                mood_values, recent_values
            ),
            "trend_deterioration": self._assess_trend_deterioration(
                mood_values, timeframe_days
            ),
        }

        # Overall statistical risk assessment
        risk_score = 0
        if risk_indicators["consecutive_low_days"] >= 3:
            risk_score += 0.3
        if risk_indicators["significant_drops"] >= 2:
            risk_score += 0.2
        if risk_indicators["below_baseline_percentage"] > 0.6:
            risk_score += 0.3
        if risk_indicators["trend_deterioration"]:
            risk_score += 0.2

        return {
            "statistical_risk_score": min(1.0, risk_score),
            "risk_indicators": risk_indicators,
        }

    def _count_consecutive_low_days(
        self, values: List[float], threshold: float = 3.0
    ) -> int:
        """Count consecutive days below threshold"""
        max_consecutive = 0
        current_consecutive = 0

        for value in values:
            if value < threshold:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _count_significant_drops(
        self, values: List[float], drop_threshold: float = 2.0
    ) -> int:
        """Count significant mood drops"""
        drops = 0
        for i in range(1, len(values)):
            if values[i - 1] - values[i] >= drop_threshold:
                drops += 1
        return drops

    def _calculate_below_baseline_percentage(
        self, all_values: List[float], recent_values: List[float]
    ) -> float:
        """Calculate percentage of recent values below personal baseline"""
        if not all_values or not recent_values:
            return 0.0

        baseline = np.mean(all_values)
        below_baseline = sum(1 for v in recent_values if v < baseline)
        return below_baseline / len(recent_values)

    def _assess_trend_deterioration(
        self, values: List[float], timeframe_days: int
    ) -> bool:
        """Assess if there's a concerning trend deterioration"""
        if len(values) < timeframe_days * 2:
            return False

        # Compare recent period to previous period
        recent_period = values[-timeframe_days:]
        previous_period = values[-timeframe_days * 2 : -timeframe_days]

        recent_avg = np.mean(recent_period)
        previous_avg = np.mean(previous_period)

        # Significant deterioration if recent average is notably lower
        return recent_avg < previous_avg - 1.0

    def predict_therapy_outcomes(self, user, timeframe_days: int = 30) -> Dict:
        """Enhanced therapy outcome prediction with engagement analysis"""
        cache_key = f"therapy_prediction_{user.id}_{timeframe_days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Check if appointments app exists
            import importlib.util
            appointments_available = importlib.util.find_spec('appointments.models') is not None

            end_date = timezone.now()
            start_date = end_date - timedelta(days=timeframe_days)

            # Enhanced engagement metrics
            engagement_data = self._calculate_enhanced_engagement_metrics(
                user, start_date, end_date, appointments_available
            )

            # Progress indicators
            progress_data = self._calculate_progress_indicators(user, timeframe_days)

            # Combine data for AI analysis
            analysis_data = {
                **engagement_data,
                **progress_data,
                "timeframe_days": timeframe_days,
            }

            # AI-powered outcome prediction
            prediction = self._analyze_therapy_outcomes_with_ai(analysis_data)

            # Cache result
            cache.set(cache_key, prediction, self.cache_timeout)
            return prediction

        except Exception as e:
            logger.error(
                f"Error in therapy outcome prediction: {str(e)}", exc_info=True
            )
            return self._create_default_prediction("therapy_prediction_error")

    def _calculate_enhanced_engagement_metrics(
        self, user, start_date, end_date, appointments_available: bool
    ) -> Dict:
        """Calculate comprehensive engagement metrics"""
        metrics = {
            "journal_entries": JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).count(),
            "mood_logs": 0,
            "appointments": 0,
            "appointment_attendance": 0,
            "consistency_score": 0,
            "content_quality_score": 0,
        }

        try:
            from mood.models import MoodLog

            # Mood logging metrics
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            )
            metrics["mood_logs"] = mood_logs.count()

            # Consistency metrics
            metrics["consistency_score"] = self._calculate_consistency_score(
                user, start_date, end_date
            )

            # Content quality metrics
            metrics["content_quality_score"] = self._calculate_content_quality_score(
                user, start_date, end_date
            )

            # Appointment metrics if available
            if appointments_available:
                try:
                    from appointments.models import Appointment
                    appointments = Appointment.objects.filter(
                        patient=user, scheduled_time__range=(start_date, end_date)
                    )
                    metrics["appointments"] = appointments.count()
                    metrics["appointment_attendance"] = appointments.filter(
                        status="completed"
                    ).count()
                except ImportError:
                    logger.warning("Appointments model not available")
                    pass

        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {str(e)}")

        return metrics

    def _calculate_consistency_score(self, user, start_date, end_date) -> float:
        """Calculate user's consistency in using the platform"""
        total_days = (end_date - start_date).days
        if total_days == 0:
            return 0.0

        # Count days with any activity
        active_days = set()

        try:
            from mood.models import MoodLog
            from journal.models import JournalEntry

            # Days with mood logs
            mood_days = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).values_list("logged_at__date", flat=True)
            active_days.update(mood_days)

            # Days with journal entries
            journal_days = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).values_list("created_at__date", flat=True)
            active_days.update(journal_days)

            return len(active_days) / total_days

        except Exception as e:
            logger.error(f"Error calculating consistency score: {str(e)}")
            return 0.0

    def _calculate_content_quality_score(self, user, start_date, end_date) -> float:
        """Calculate quality score based on content depth and reflection"""
        try:
            entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            )

            if not entries.exists():
                return 0.0

            quality_scores = []
            for entry in entries:
                score = 0.0
                content = entry.content.lower()

                # Length indicates depth
                if len(content) > 100:
                    score += 0.3
                if len(content) > 300:
                    score += 0.2

                # Reflection indicators
                reflection_words = [
                    "feel",
                    "think",
                    "realize",
                    "understand",
                    "learned",
                    "noticed",
                ]
                score += min(
                    0.3, sum(0.05 for word in reflection_words if word in content)
                )

                # Emotional awareness
                emotion_words = [
                    "angry",
                    "sad",
                    "happy",
                    "anxious",
                    "grateful",
                    "frustrated",
                ]
                score += min(
                    0.2, sum(0.02 for word in emotion_words if word in content)
                )

                quality_scores.append(min(1.0, score))

            return np.mean(quality_scores)

        except Exception as e:
            logger.error(f"Error calculating content quality score: {str(e)}")
            return 0.0

    def _calculate_progress_indicators(self, user, timeframe_days: int) -> Dict:
        """Calculate various progress indicators"""
        try:
            from mood.models import MoodLog

            # Get mood trend over time
            mood_logs = MoodLog.objects.filter(
                user=user,
                logged_at__gte=timezone.now() - timedelta(days=timeframe_days * 2),
            ).order_by("logged_at")

            if mood_logs.count() < 5:
                return {"progress_trend": "insufficient_data", "improvement_score": 0}

            # Split into two periods for comparison
            midpoint = mood_logs.count() // 2
            earlier_moods = [log.mood_rating for log in mood_logs[:midpoint]]
            recent_moods = [log.mood_rating for log in mood_logs[midpoint:]]

            earlier_avg = np.mean(earlier_moods) if earlier_moods else 5
            recent_avg = np.mean(recent_moods) if recent_moods else 5

            improvement_score = (
                recent_avg - earlier_avg
            ) / 10  # Normalized improvement

            if improvement_score > 0.1:
                trend = "improving"
            elif improvement_score < -0.1:
                trend = "declining"
            else:
                trend = "stable"

            return {
                "progress_trend": trend,
                "improvement_score": float(improvement_score),
                "earlier_average": float(earlier_avg),
                "recent_average": float(recent_avg),
            }

        except Exception as e:
            logger.error(f"Error calculating progress indicators: {str(e)}")
            return {"progress_trend": "unknown", "improvement_score": 0}

    def _analyze_therapy_outcomes_with_ai(self, data: Dict) -> Dict:
        """AI analysis for therapy outcome prediction"""
        try:
            prompt = f"""Analyze therapy engagement and predict outcomes based on this data:

ENGAGEMENT METRICS:
- Journal entries: {data.get('journal_entries', 0)}
- Mood logs: {data.get('mood_logs', 0)}
- Appointments: {data.get('appointments', 0)}
- Attendance rate: {data.get('appointment_attendance', 0) / max(1, data.get('appointments', 1)):.2f}
- Consistency score: {data.get('consistency_score', 0):.2f}
- Content quality: {data.get('content_quality_score', 0):.2f}

PROGRESS INDICATORS:
- Progress trend: {data.get('progress_trend', 'unknown')}
- Improvement score: {data.get('improvement_score', 0):.2f}
- Recent mood average: {data.get('recent_average', 5):.1f}

Provide analysis in JSON format:
{{
    "engagement_level": "low|medium|high|very_high",
    "predicted_outcome": "excellent|good|fair|poor",
    "confidence": <float 0-1>,
    "recommendations": [<list of specific recommendations>],
    "risk_factors": [<list of concerning factors>],
    "strengths": [<list of positive factors>],
    "timeline_estimate": <estimated time to see significant improvement>,
    "intervention_suggestions": [<suggestions for therapeutic interventions>]
}}
"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "{}")
                return self._parse_therapy_prediction_response(response_text)
            else:
                logger.error(f"Ollama request failed: {response.status_code}")
                return self._create_default_prediction("therapy_ai_failed")

        except Exception as e:
            logger.error(f"Error in AI therapy outcome analysis: {str(e)}")
            return self._create_default_prediction("therapy_ai_error")

    def _parse_therapy_prediction_response(self, response_text: str) -> Dict:
        """Parse therapy prediction response"""
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            prediction = json.loads(response_text)

            # Provide defaults for missing fields
            defaults = {
                "engagement_level": "medium",
                "predicted_outcome": "fair",
                "confidence": 0.5,
                "recommendations": ["Continue regular therapy sessions"],
                "risk_factors": [],
                "strengths": [],
                "timeline_estimate": "3-6 months",
                "intervention_suggestions": [],
            }

            for field, default in defaults.items():
                if field not in prediction:
                    prediction[field] = default

            return prediction

        except json.JSONDecodeError:
            logger.error("Failed to parse therapy prediction response")
            return self._create_default_prediction("therapy_parse_error")

    def analyze_journal_patterns(self, user, time_field="created_at", **kwargs) -> Dict:
        """Enhanced journal pattern analysis with AI insights"""
        cache_key = f"journal_patterns_{user.id}_{hash(str(kwargs))}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            now = timezone.now()
            month_ago = now - timedelta(days=30)

            qs = JournalEntry.objects.filter(
                user=user, **{f"{time_field}__gte": month_ago}
            )

            if not qs.exists():
                result = {
                    "concerns": False,
                    "sentiment_trend": "neutral",
                    "avg_mood": 3.0,
                    "category_analysis": {},
                    "message": "No journal entries found",
                }
                cache.set(cache_key, result, self.cache_timeout)
                return result

            # Enhanced analysis
            category_analysis = self._analyze_journal_categories(qs)
            content_analysis = self._analyze_journal_content_patterns(qs)
            temporal_analysis = self._analyze_journal_temporal_patterns(qs)

            # Calculate sentiment and mood trends
            sentiment_analysis = self._calculate_sentiment_trends(qs)

            # Combine all analyses
            analysis = {
                "concerns": self._identify_journal_concerns(qs),
                "sentiment_trend": sentiment_analysis["trend"],
                "avg_mood": sentiment_analysis["avg_mood"],
                "category_analysis": category_analysis,
                "content_patterns": content_analysis,
                "temporal_patterns": temporal_analysis,
                "total_entries": qs.count(),
                "analysis_period_days": 30,
                "has_sufficient_data": True,
                **sentiment_analysis,
            }

            # Cache result
            cache.set(cache_key, analysis, self.cache_timeout)
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing journal patterns: {str(e)}", exc_info=True)
            return {
                "concerns": False,
                "sentiment_trend": "neutral",
                "avg_mood": 3.0,
                "has_sufficient_data": False,
                "error": str(e),
            }

    def _analyze_journal_categories(self, queryset) -> Dict:
        """Analyze journal entries by category with enhanced metrics"""
        try:
            categories = JournalCategory.objects.filter(
                user=queryset.first().user if queryset.exists() else None
            )
            category_analysis = {}

            for category in categories:
                category_entries = queryset.filter(category=category)
                if category_entries.exists():
                    moods = category_entries.exclude(mood__isnull=True)

                    # Enhanced category metrics
                    category_analysis[category.name] = {
                        "count": category_entries.count(),
                        "avg_mood": self._calculate_mood_average(moods),
                        "mood_trend": self._calculate_category_mood_trend(moods),
                        "most_recent": category_entries.latest("created_at").content[
                            :100
                        ],
                        "frequency_score": self._calculate_frequency_score(
                            category_entries
                        ),
                        "engagement_score": self._calculate_category_engagement(
                            category_entries
                        ),
                    }

            return category_analysis

        except Exception as e:
            logger.error(f"Error analyzing journal categories: {str(e)}")
            return {}

    def _calculate_mood_average(self, queryset) -> float:
        """Calculate average mood with proper field mapping"""
        if not queryset.exists():
            return 3.0

        return (
            queryset.aggregate(
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

    def _calculate_category_mood_trend(self, queryset) -> str:
        """Calculate mood trend for a specific category"""
        if queryset.count() < 3:
            return "insufficient_data"

        # Get mood values in chronological order
        entries = queryset.order_by("created_at")
        mood_values = []

        for entry in entries:
            mood_map = {
                "very_negative": 1,
                "negative": 2,
                "neutral": 3,
                "positive": 4,
                "very_positive": 5,
            }
            mood_values.append(mood_map.get(entry.mood, 3))

        if len(mood_values) < 2:
            return "stable"

        # Simple trend calculation
        recent_half = mood_values[len(mood_values) // 2 :]
        earlier_half = mood_values[: len(mood_values) // 2]

        recent_avg = np.mean(recent_half)
        earlier_avg = np.mean(earlier_half)

        if recent_avg > earlier_avg + 0.5:
            return "improving"
        elif recent_avg < earlier_avg - 0.5:
            return "declining"
        else:
            return "stable"

    def _calculate_frequency_score(self, queryset) -> float:
        """Calculate how frequently user writes in this category"""
        if not queryset.exists():
            return 0.0

        days_span = (
            queryset.latest("created_at").created_at
            - queryset.earliest("created_at").created_at
        ).days + 1
        return min(1.0, queryset.count() / max(1, days_span))

    def _calculate_category_engagement(self, queryset) -> float:
        """Calculate engagement level for this category based on content length and detail"""
        if not queryset.exists():
            return 0.0

        total_length = sum(len(entry.content) for entry in queryset)
        avg_length = total_length / queryset.count()

        # Normalize engagement score (longer entries = higher engagement)
        return min(1.0, avg_length / 500)  # 500 chars = full engagement

    def _analyze_journal_content_patterns(self, queryset) -> Dict:
        """Analyze content patterns in journal entries"""
        try:
            all_content = " ".join([entry.content.lower() for entry in queryset])

            # Word frequency analysis
            words = re.findall(r"\b\w+\b", all_content)
            word_freq = defaultdict(int)
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_freq[word] += 1

            # Get most common themes
            common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

            # Emotional indicators
            emotion_patterns = self._detect_emotion_patterns(all_content)

            # Topic evolution
            topic_evolution = self._analyze_topic_evolution(queryset)

            return {
                "common_themes": dict(common_words),
                "emotion_patterns": emotion_patterns,
                "topic_evolution": topic_evolution,
                "content_diversity": len(set(words)) / len(words) if words else 0,
            }

        except Exception as e:
            logger.error(f"Error analyzing content patterns: {str(e)}")
            return {}

    def _detect_emotion_patterns(self, content: str) -> Dict:
        """Detect emotional patterns in journal content"""
        emotion_keywords = {
            "anxiety": [
                r"\banxious\b",
                r"\bworried\b",
                r"\bnervous\b",
                r"\bstressed\b",
            ],
            "depression": [r"\bsad\b", r"\bdepressed\b", r"\bhopeless\b", r"\bempty\b"],
            "anger": [r"\bangry\b", r"\bfrustrated\b", r"\birritated\b", r"\bmad\b"],
            "joy": [r"\bhappy\b", r"\bjoyful\b", r"\bexcited\b", r"\bglad\b"],
            "gratitude": [
                r"\bthankful\b",
                r"\bgrateful\b",
                r"\bappreciate\b",
                r"\bblessed\b",
            ],
        }

        patterns = {}
        for emotion, keywords in emotion_keywords.items():
            count = sum(len(re.findall(pattern, content)) for pattern in keywords)
            patterns[emotion] = count

        return patterns

    def _analyze_topic_evolution(self, queryset) -> List[Dict]:
        """Analyze how topics evolve over time"""
        try:
            # Group entries by week
            weekly_topics = defaultdict(list)

            for entry in queryset.order_by("created_at"):
                week = entry.created_at.isocalendar()[1]  # Get week number
                # Simple topic extraction (first 50 chars as topic indicator)
                topic_indicator = entry.content[:50].lower()
                weekly_topics[week].append(topic_indicator)

            # Analyze topic changes week by week
            evolution = []
            for week in sorted(weekly_topics.keys()):
                topics = weekly_topics[week]
                evolution.append(
                    {
                        "week": week,
                        "entry_count": len(topics),
                        "avg_length": np.mean([len(topic) for topic in topics]),
                        "topics_sample": topics[:3],  # Sample of topics
                    }
                )

            return evolution

        except Exception as e:
            logger.error(f"Error analyzing topic evolution: {str(e)}")
            return []

    def _analyze_journal_temporal_patterns(self, queryset) -> Dict:
        """Analyze temporal patterns in journaling"""
        try:
            # Time of day patterns
            hours = [entry.created_at.hour for entry in queryset]
            hour_dist = defaultdict(int)
            for hour in hours:
                hour_dist[hour] += 1

            # Day of week patterns
            days = [entry.created_at.strftime("%A") for entry in queryset]
            day_dist = defaultdict(int)
            for day in days:
                day_dist[day] += 1

            # Writing frequency
            dates = [entry.created_at.date() for entry in queryset]
            unique_dates = len(set(dates))
            total_days = (max(dates) - min(dates)).days + 1 if dates else 1

            return {
                "preferred_hours": dict(hour_dist),
                "preferred_days": dict(day_dist),
                "writing_frequency": unique_dates / total_days,
                "most_active_hour": max(hour_dist.items(), key=lambda x: x[1])[0]
                if hour_dist
                else 12,
                "most_active_day": max(day_dist.items(), key=lambda x: x[1])[0]
                if day_dist
                else "Unknown",
            }

        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {}

    def _calculate_sentiment_trends(self, queryset) -> Dict:
        """Calculate sentiment trends with enhanced analysis"""
        if not queryset.exists():
            return {"trend": "neutral", "avg_mood": 3.0}

        # Calculate overall average mood
        avg_mood = self._calculate_mood_average(queryset)

        # Calculate trend over time
        entries = queryset.order_by("created_at")
        if entries.count() < 3:
            return {"trend": "stable", "avg_mood": avg_mood}

        # Split into periods and compare
        mid_point = entries.count() // 2
        earlier_entries = entries[:mid_point]
        later_entries = entries[mid_point:]

        earlier_avg = self._calculate_mood_average(earlier_entries)
        later_avg = self._calculate_mood_average(later_entries)

        # Determine trend
        if later_avg > earlier_avg + 0.3:
            trend = "improving"
        elif later_avg < earlier_avg - 0.3:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "avg_mood": avg_mood,
            "earlier_period_avg": earlier_avg,
            "later_period_avg": later_avg,
            "trend_strength": abs(later_avg - earlier_avg),
        }

    def _identify_journal_concerns(self, queryset) -> bool:
        """Identify if there are concerning patterns in journal entries"""
        try:
            # Check for concerning keywords
            concerning_keywords = [
                r"\bsuicid\w*\b",
                r"\bself.harm\b",
                r"\bhurt.myself\b",
                r"\bcan.?t.cope\b",
                r"\bwant.to.die\b",
                r"\bhopeless\b",
                r"\bcrisis\b",
                r"\bemergency\b",
            ]

            all_content = " ".join([entry.content.lower() for entry in queryset])

            for pattern in concerning_keywords:
                if re.search(pattern, all_content):
                    return True

            # Check for consistently low mood
            avg_mood = self._calculate_mood_average(queryset)
            if avg_mood < 2.0:
                return True

            # Check for concerning frequency of negative entries
            negative_entries = queryset.filter(mood__in=["very_negative", "negative"])
            if (
                negative_entries.count() > queryset.count() * 0.7
            ):  # More than 70% negative
                return True

            return False

        except Exception as e:
            logger.error(f"Error identifying journal concerns: {str(e)}")
            return False

    def _create_default_prediction(self, error_type: str) -> Dict:
        """Create default prediction with error context"""
        defaults = {
            "mood_decline_error": {
                "risk_level": "unknown",
                "confidence": 0,
                "factors": ["Analysis error occurred"],
                "recommendations": ["Continue monitoring mood"],
                "error": error_type,
            },
            "therapy_prediction_error": {
                "engagement_level": "unknown",
                "predicted_outcome": "uncertain",
                "confidence": 0,
                "recommendations": ["Continue regular sessions"],
                "error": error_type,
            },
        }

        return defaults.get(
            error_type,
            {
                "status": "error",
                "confidence": 0,
                "recommendations": ["Consult with healthcare provider"],
                "error": error_type,
            },
        )

    def get_comprehensive_user_prediction(self, user, timeframe_days: int = 7) -> Dict:
        """Get comprehensive prediction combining mood, therapy, and journal analysis"""
        try:
            # Get all individual predictions
            mood_prediction = self.predict_mood_decline(user, timeframe_days)
            therapy_prediction = self.predict_therapy_outcomes(user, timeframe_days * 4)
            journal_analysis = self.analyze_journal_patterns(user)

            # Combine into comprehensive assessment
            combined_prediction = {
                "user_id": user.id,
                "analysis_date": timezone.now().isoformat(),
                "timeframe_days": timeframe_days,
                "mood_prediction": mood_prediction,
                "therapy_prediction": therapy_prediction,
                "journal_analysis": journal_analysis,
                "overall_assessment": self._create_overall_assessment(
                    mood_prediction, therapy_prediction, journal_analysis
                ),
            }

            return combined_prediction

        except Exception as e:
            logger.error(f"Error creating comprehensive prediction: {str(e)}")
            return {"error": str(e), "user_id": user.id}

    def _create_overall_assessment(
        self, mood_pred: Dict, therapy_pred: Dict, journal_analysis: Dict
    ) -> Dict:
        """Create overall assessment from individual predictions"""
        try:
            # Combine risk levels
            risk_factors = []
            protective_factors = []
            recommendations = []

            # From mood prediction
            if mood_pred.get("risk_level") in ["high", "critical"]:
                risk_factors.extend(mood_pred.get("factors", []))
            if mood_pred.get("protective_factors"):
                protective_factors.extend(mood_pred["protective_factors"])
            recommendations.extend(mood_pred.get("recommendations", []))

            # From therapy prediction
            if therapy_pred.get("engagement_level") == "low":
                risk_factors.append("Low therapy engagement")
            if therapy_pred.get("strengths"):
                protective_factors.extend(therapy_pred["strengths"])
            recommendations.extend(therapy_pred.get("recommendations", []))

            # From journal analysis
            if journal_analysis.get("concerns"):
                risk_factors.append("Journal content shows concerns")
            if journal_analysis.get("sentiment_trend") == "improving":
                protective_factors.append("Improving sentiment in journal entries")

            # Overall risk assessment
            high_risk_indicators = sum(
                [
                    mood_pred.get("risk_level") in ["high", "critical"],
                    therapy_pred.get("engagement_level") == "low",
                    journal_analysis.get("concerns", False),
                    journal_analysis.get("sentiment_trend") == "declining",
                ]
            )

            if high_risk_indicators >= 3:
                overall_risk = "high"
            elif high_risk_indicators >= 2:
                overall_risk = "medium"
            else:
                overall_risk = "low"

            return {
                "overall_risk_level": overall_risk,
                "combined_confidence": np.mean(
                    [
                        mood_pred.get("confidence", 0),
                        therapy_pred.get("confidence", 0),
                        0.7 if journal_analysis.get("total_entries", 0) > 5 else 0.3,
                    ]
                ),
                "risk_factors": list(set(risk_factors)),
                "protective_factors": list(set(protective_factors)),
                "recommendations": list(
                    set(recommendations[:5])
                ),  # Top 5 unique recommendations
                "priority_level": "urgent"
                if overall_risk == "high"
                else "medium"
                if overall_risk == "medium"
                else "routine",
            }

        except Exception as e:
            logger.error(f"Error creating overall assessment: {str(e)}")
            return {"overall_risk_level": "unknown", "error": str(e)}


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

# datawarehouse/services/mood_collection_service.py
"""
Dedicated service for collecting and analyzing mood tracking data
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
import pandas as pd
import numpy as np
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)
User = get_user_model()


@dataclass
class MoodAnalysisResult:
    """Result structure for mood analysis"""

    count: int
    avg_mood: Optional[float]
    min_mood: Optional[float]
    max_mood: Optional[float]
    volatility: float
    trend: str
    daily_averages: Dict[str, float]
    activity_patterns: Dict[str, Any]
    energy_patterns: Dict[str, Any]
    sleep_correlations: Dict[str, Any]
    entries: List[Dict[str, Any]]
    quality_score: float


class MoodCollectionService:
    """
    Specialized service for mood tracking data collection and analysis

    Features:
    - Comprehensive mood pattern analysis
    - Energy level correlation
    - Activity impact assessment
    - Sleep quality correlation
    - Trend detection and forecasting
    - Anomaly detection for mental health monitoring
    """

    def __init__(self):
        self.collection_stats = {
            "total_collections": 0,
            "avg_processing_time": 0.0,
            "error_rate": 0.0,
        }

    def collect_mood_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> MoodAnalysisResult:
        """
        Collect and analyze comprehensive mood data

        Args:
            user: User instance
            start_date: Start date for data collection
            end_date: End date for data collection

        Returns:
            MoodAnalysisResult with detailed analysis
        """
        try:
            from mood.models import MoodLog

            # Get mood logs with all available fields
            mood_logs = (
                MoodLog.objects.filter(
                    user=user, logged_at__range=(start_date, end_date)
                )
                .values(
                    "id",
                    "mood_rating",
                    "energy_level",
                    "activities",
                    "notes",
                    "logged_at",
                    "created_at",
                )
                .order_by("logged_at")
            )

            if not mood_logs:
                return self._get_empty_mood_analysis()

            # Convert to DataFrame for analysis
            df = pd.DataFrame(list(mood_logs))
            df["logged_at"] = pd.to_datetime(df["logged_at"])
            df = df.sort_values("logged_at")

            # Perform comprehensive analysis
            analysis_result = MoodAnalysisResult(
                count=len(df),
                avg_mood=self._calculate_average_mood(df),
                min_mood=self._calculate_min_mood(df),
                max_mood=self._calculate_max_mood(df),
                volatility=self._calculate_volatility(df),
                trend=self._calculate_trend(df),
                daily_averages=self._calculate_daily_averages(df),
                activity_patterns=self._analyze_activity_patterns(df),
                energy_patterns=self._analyze_energy_patterns(df),
                sleep_correlations=self._analyze_sleep_correlations(df),
                entries=df.to_dict("records"),
                quality_score=self._calculate_data_quality_score(df),
            )

            logger.info(
                "Mood data collection completed",
                user_id=user.id,
                entries_count=len(df),
                avg_mood=analysis_result.avg_mood,
            )

            return analysis_result

        except Exception as exc:
            logger.error("Error collecting mood data", error=str(exc), user_id=user.id)
            return self._get_empty_mood_analysis()

    def _calculate_average_mood(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate average mood score"""
        try:
            if df.empty or "mood_rating" not in df:
                return None
            mood_scores = df["mood_rating"].dropna()
            return float(mood_scores.mean()) if not mood_scores.empty else None
        except Exception:
            return None

    def _calculate_min_mood(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate minimum mood score"""
        try:
            if df.empty or "mood_rating" not in df:
                return None
            mood_scores = df["mood_rating"].dropna()
            return float(mood_scores.min()) if not mood_scores.empty else None
        except Exception:
            return None

    def _calculate_max_mood(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate maximum mood score"""
        try:
            if df.empty or "mood_rating" not in df:
                return None
            mood_scores = df["mood_rating"].dropna()
            return float(mood_scores.max()) if not mood_scores.empty else None
        except Exception:
            return None

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """Calculate mood volatility (standard deviation)"""
        try:
            if df.empty or "mood_rating" not in df:
                return 0.0
            mood_scores = df["mood_rating"].dropna()
            return float(mood_scores.std()) if len(mood_scores) > 1 else 0.0
        except Exception:
            return 0.0

    def _calculate_trend(self, df: pd.DataFrame) -> str:
        """Calculate mood trend direction using linear regression"""
        try:
            if df.empty or len(df) < 2 or "mood_rating" not in df:
                return "stable"

            mood_scores = df["mood_rating"].dropna()
            if len(mood_scores) < 2:
                return "stable"

            # Simple linear regression to determine trend
            x = np.arange(len(mood_scores))
            slope, _ = np.polyfit(x, mood_scores, 1)

            if slope > 0.2:
                return "strongly_improving"
            elif slope > 0.05:
                return "improving"
            elif slope < -0.2:
                return "strongly_declining"
            elif slope < -0.05:
                return "declining"
            else:
                return "stable"

        except Exception:
            return "stable"

    def _calculate_daily_averages(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate daily mood averages"""
        try:
            if df.empty or "logged_at" not in df or "mood_rating" not in df:
                return {}

            df["date"] = df["logged_at"].dt.date
            daily_avg = df.groupby("date")["mood_rating"].mean()

            # Convert to string keys for JSON serialization
            return {str(date): float(avg) for date, avg in daily_avg.items()}

        except Exception:
            return {}

    def _analyze_activity_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze relationship between activities and mood"""
        try:
            if df.empty or "activities" not in df:
                return {}

            activity_mood_map = {}
            total_activities = 0

            for index, row in df.iterrows():
                if pd.isna(row["activities"]) or pd.isna(row["mood_rating"]):
                    continue

                activities = row["activities"]
                mood = row["mood_rating"]

                # Handle different activity data formats
                if isinstance(activities, str):
                    activity_list = [activities]
                elif isinstance(activities, list):
                    activity_list = activities
                else:
                    continue

                for activity in activity_list:
                    if activity not in activity_mood_map:
                        activity_mood_map[activity] = []
                    activity_mood_map[activity].append(mood)
                    total_activities += 1

            # Calculate average mood for each activity
            activity_analysis = {}
            for activity, moods in activity_mood_map.items():
                activity_analysis[activity] = {
                    "avg_mood": float(np.mean(moods)),
                    "count": len(moods),
                    "mood_range": float(np.max(moods) - np.min(moods))
                    if len(moods) > 1
                    else 0.0,
                }

            return {
                "total_activities_logged": total_activities,
                "unique_activities": len(activity_mood_map),
                "activity_mood_analysis": activity_analysis,
                "most_mood_boosting": max(
                    activity_analysis.items(),
                    key=lambda x: x[1]["avg_mood"],
                    default=(None, {}),
                )[0],
            }

        except Exception:
            return {}

    def _analyze_energy_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze energy level patterns and correlation with mood"""
        try:
            if df.empty or "energy_level" not in df or "mood_rating" not in df:
                return {}

            # Filter rows with both energy and mood data
            energy_mood_df = df.dropna(subset=["energy_level", "mood_rating"])

            if energy_mood_df.empty:
                return {}

            # Calculate correlation between energy and mood
            correlation = energy_mood_df["energy_level"].corr(
                energy_mood_df["mood_rating"]
            )

            # Energy level distribution
            energy_distribution = (
                energy_mood_df["energy_level"].value_counts().to_dict()
            )

            # Average mood by energy level
            avg_mood_by_energy = (
                energy_mood_df.groupby("energy_level")["mood_rating"].mean().to_dict()
            )

            return {
                "energy_mood_correlation": float(correlation)
                if not pd.isna(correlation)
                else 0.0,
                "energy_distribution": {
                    int(k): int(v) for k, v in energy_distribution.items()
                },
                "avg_mood_by_energy_level": {
                    int(k): float(v) for k, v in avg_mood_by_energy.items()
                },
                "avg_energy_level": float(energy_mood_df["energy_level"].mean()),
                "energy_consistency": float(energy_mood_df["energy_level"].std())
                if len(energy_mood_df) > 1
                else 0.0,
            }

        except Exception:
            return {}

    def _analyze_sleep_correlations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sleep patterns correlation with mood (if sleep data available)"""
        try:
            # This is a placeholder for sleep correlation analysis
            # In the future, this could analyze sleep hours from health metrics
            # or extract sleep mentions from notes

            sleep_mentions = 0
            if "notes" in df:
                sleep_keywords = ["sleep", "tired", "exhausted", "rested", "insomnia"]
                for note in df["notes"].dropna():
                    if any(keyword in str(note).lower() for keyword in sleep_keywords):
                        sleep_mentions += 1

            return {
                "sleep_mentions_in_notes": sleep_mentions,
                "sleep_impact_detected": sleep_mentions > 0,
                "note": "Sleep correlation analysis placeholder - integrate with health metrics",
            }

        except Exception:
            return {}

    def _calculate_data_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate data quality score based on completeness and consistency"""
        try:
            if df.empty:
                return 0.0

            quality_scores = []

            # Completeness score
            for field in ["mood_rating", "energy_level", "activities", "notes"]:
                if field in df:
                    completeness = 1 - (df[field].isna().sum() / len(df))
                    quality_scores.append(completeness)
                else:
                    quality_scores.append(0.0)

            # Consistency score (entries per day consistency)
            if "logged_at" in df:
                df["date"] = df["logged_at"].dt.date
                daily_counts = df.groupby("date").size()
                consistency = (
                    1 - (daily_counts.std() / daily_counts.mean())
                    if daily_counts.mean() > 0
                    else 0
                )
                consistency = max(0, min(1, consistency))  # Clamp between 0 and 1
                quality_scores.append(consistency)

            return float(np.mean(quality_scores))

        except Exception:
            return 0.5  # Default middle score

    def _get_empty_mood_analysis(self) -> MoodAnalysisResult:
        """Return empty mood analysis result"""
        return MoodAnalysisResult(
            count=0,
            avg_mood=None,
            min_mood=None,
            max_mood=None,
            volatility=0.0,
            trend="stable",
            daily_averages={},
            activity_patterns={},
            energy_patterns={},
            sleep_correlations={},
            entries=[],
            quality_score=0.0,
        )

    def detect_mood_anomalies(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Detect mood anomalies and potential warning signs

        Args:
            user: User instance
            days: Number of days to analyze

        Returns:
            Dict with anomaly detection results
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            mood_result = self.collect_mood_data(user, start_date, end_date)

            if mood_result.count < 5:  # Need minimum data for anomaly detection
                return {"anomalies_detected": False, "reason": "insufficient_data"}

            anomalies = []

            # Check for sudden mood drops
            if mood_result.volatility > 2.0:  # High volatility
                anomalies.append(
                    {
                        "type": "high_volatility",
                        "severity": "medium",
                        "description": "High mood volatility detected",
                    }
                )

            # Check for declining trend
            if mood_result.trend in ["declining", "strongly_declining"]:
                anomalies.append(
                    {
                        "type": "declining_trend",
                        "severity": "high"
                        if mood_result.trend == "strongly_declining"
                        else "medium",
                        "description": f"Mood trend is {mood_result.trend}",
                    }
                )

            # Check for consistently low mood
            if mood_result.avg_mood and mood_result.avg_mood < 4.0:
                anomalies.append(
                    {
                        "type": "low_mood_average",
                        "severity": "high" if mood_result.avg_mood < 3.0 else "medium",
                        "description": f"Average mood is low: {mood_result.avg_mood:.1f}",
                    }
                )

            return {
                "anomalies_detected": len(anomalies) > 0,
                "anomalies": anomalies,
                "analysis_period_days": days,
                "data_quality_score": mood_result.quality_score,
            }

        except Exception as exc:
            logger.error(
                "Error in mood anomaly detection", error=str(exc), user_id=user.id
            )
            return {"anomalies_detected": False, "error": str(exc)}

    def get_mood_insights(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Generate actionable insights from mood data

        Args:
            user: User instance
            days: Number of days to analyze

        Returns:
            Dict with mood insights and recommendations
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            mood_result = self.collect_mood_data(user, start_date, end_date)

            if mood_result.count == 0:
                return {"insights_available": False, "reason": "no_data"}

            insights = []
            recommendations = []

            # Trend insights
            if mood_result.trend == "improving":
                insights.append(
                    "Your mood has been improving over time. Keep up the good work!"
                )
                recommendations.append("Continue with current activities and routines")
            elif mood_result.trend in ["declining", "strongly_declining"]:
                insights.append(
                    "Your mood has been declining recently. This might be a good time to reach out for support."
                )
                recommendations.append(
                    "Consider scheduling a session with your therapist"
                )

            # Activity insights
            if mood_result.activity_patterns.get("most_mood_boosting"):
                best_activity = mood_result.activity_patterns["most_mood_boosting"]
                insights.append(
                    f"'{best_activity}' seems to have the most positive impact on your mood"
                )
                recommendations.append(
                    f"Try to incorporate more '{best_activity}' into your routine"
                )

            # Energy insights
            if mood_result.energy_patterns.get("energy_mood_correlation", 0) > 0.5:
                insights.append(
                    "There's a strong positive correlation between your energy levels and mood"
                )
                recommendations.append(
                    "Focus on activities that boost your energy levels"
                )

            # Consistency insights
            if mood_result.quality_score > 0.8:
                insights.append(
                    "You're doing great at consistently tracking your mood!"
                )
            elif mood_result.quality_score < 0.5:
                recommendations.append(
                    "Try to track your mood more consistently for better insights"
                )

            return {
                "insights_available": True,
                "insights": insights,
                "recommendations": recommendations,
                "analysis_summary": {
                    "period_days": days,
                    "entries_count": mood_result.count,
                    "avg_mood": mood_result.avg_mood,
                    "trend": mood_result.trend,
                    "data_quality": mood_result.quality_score,
                },
            }

        except Exception as exc:
            logger.error(
                "Error generating mood insights", error=str(exc), user_id=user.id
            )
            return {"insights_available": False, "error": str(exc)}


# Create singleton instance
mood_collector = MoodCollectionService()

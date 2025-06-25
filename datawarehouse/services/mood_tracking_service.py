# datawarehouse/services/mood_tracking_service.py
"""
Dedicated service for collecting and processing mood tracking data
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class MoodDataSnapshot:
    """Structured representation of mood data"""

    user_id: int
    collection_date: datetime
    period_days: int
    mood_statistics: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    activity_patterns: Dict[str, Any]
    sleep_analysis: Dict[str, Any]
    energy_analysis: Dict[str, Any]
    stress_analysis: Dict[str, Any]
    raw_entries: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class MoodTrackingCollectionService:
    """Dedicated service for mood tracking data collection and analysis"""

    def __init__(self):
        self.cache_timeout = 900  # 15 minutes
        self.collection_stats = {
            "total_collections": 0,
            "avg_collection_time": 0.0,
            "cache_hit_rate": 0.0,
            "error_rate": 0.0,
        }

    def collect_mood_data(self, user_id: int, days: int = 30) -> MoodDataSnapshot:
        """
        Collect comprehensive mood tracking data for a user

        Args:
            user_id: User identifier
            days: Number of days to collect data for

        Returns:
            MoodDataSnapshot with all mood-related data
        """
        import time

        start_time = time.time()
        logger.info(f"Starting mood data collection for user {user_id}, {days} days")

        try:
            # Check cache first
            cache_key = f"mood_data:{user_id}:{days}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached mood data for user {user_id}")
                self.collection_stats["cache_hit_rate"] += 1
                return MoodDataSnapshot(**cached_data)

            # Get user object
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError(f"User {user_id} not found")

            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Collect mood data
            mood_data = self._collect_raw_mood_data(user, start_date, end_date)

            # Analyze mood patterns
            mood_statistics = self._calculate_mood_statistics(mood_data)
            trend_analysis = self._analyze_mood_trends(mood_data)
            activity_patterns = self._analyze_activity_patterns(mood_data)
            sleep_analysis = self._analyze_sleep_patterns(mood_data)
            energy_analysis = self._analyze_energy_patterns(mood_data)
            stress_analysis = self._analyze_stress_patterns(mood_data)

            # Create snapshot
            snapshot = MoodDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                mood_statistics=mood_statistics,
                trend_analysis=trend_analysis,
                activity_patterns=activity_patterns,
                sleep_analysis=sleep_analysis,
                energy_analysis=energy_analysis,
                stress_analysis=stress_analysis,
                raw_entries=mood_data.to_dict("records") if not mood_data.empty else [],
                metadata={
                    "collection_time": time.time() - start_time,
                    "total_entries": len(mood_data),
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "version": "1.0",
                },
            )

            # Cache the results
            from dataclasses import asdict

            cache.set(cache_key, asdict(snapshot), self.cache_timeout)

            # Update performance metrics
            self._update_performance_metrics(start_time, len(mood_data))

            logger.info(f"Mood data collection completed for user {user_id}")
            return snapshot

        except Exception as exc:
            logger.error(f"Mood data collection failed for user {user_id}: {str(exc)}")
            self.collection_stats["error_rate"] += 1
            raise

    def _collect_raw_mood_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Collect raw mood data from database"""
        try:
            from mood.models import MoodLog

            mood_logs = MoodLog.objects.filter(
                user=user, timestamp__range=(start_date, end_date)
            ).values(
                "id",
                "mood_score",
                "energy_level",
                "sleep_hours",
                "stress_level",
                "notes",
                "timestamp",
                "activities",
            )

            if not mood_logs:
                return pd.DataFrame()

            # Convert to pandas DataFrame
            df = pd.DataFrame(list(mood_logs))
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            return df

        except Exception as exc:
            logger.error(f"Error collecting raw mood data: {str(exc)}")
            return pd.DataFrame()

    def _calculate_mood_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive mood statistics"""
        try:
            if df.empty or "mood_score" not in df:
                return self._get_empty_mood_statistics()

            mood_scores = df["mood_score"].dropna()

            if mood_scores.empty:
                return self._get_empty_mood_statistics()

            statistics = {
                "count": len(mood_scores),
                "average": float(mood_scores.mean()),
                "median": float(mood_scores.median()),
                "min": float(mood_scores.min()),
                "max": float(mood_scores.max()),
                "std_deviation": float(mood_scores.std())
                if len(mood_scores) > 1
                else 0.0,
                "variance": float(mood_scores.var()) if len(mood_scores) > 1 else 0.0,
                "range": float(mood_scores.max() - mood_scores.min()),
                "mood_distribution": mood_scores.value_counts().to_dict(),
                "percentiles": {
                    "25th": float(mood_scores.quantile(0.25)),
                    "75th": float(mood_scores.quantile(0.75)),
                    "90th": float(mood_scores.quantile(0.90)),
                },
            }

            # Calculate mood categories
            if statistics["average"] >= 7:
                statistics["overall_mood_category"] = "positive"
            elif statistics["average"] >= 4:
                statistics["overall_mood_category"] = "neutral"
            else:
                statistics["overall_mood_category"] = "concerning"

            return statistics

        except Exception as exc:
            logger.error(f"Error calculating mood statistics: {str(exc)}")
            return self._get_empty_mood_statistics()

    def _analyze_mood_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze mood trends over time"""
        try:
            if df.empty or "mood_score" not in df or "timestamp" not in df:
                return {}

            # Calculate daily averages
            df["date"] = df["timestamp"].dt.date
            daily_moods = (
                df.groupby("date")["mood_score"].agg(["mean", "count"]).reset_index()
            )

            if len(daily_moods) < 2:
                return {"trend_direction": "stable", "trend_strength": 0.0}

            # Calculate trend using linear regression
            x = np.arange(len(daily_moods))
            y = daily_moods["mean"].values

            if len(x) > 1:
                slope, _ = np.polyfit(x, y, 1)  # Only need slope, ignore intercept
                correlation_matrix = np.corrcoef(x, y)
                r_value = (
                    correlation_matrix[0, 1]
                    if not np.isnan(correlation_matrix[0, 1])
                    else 0
                )
                p_value = 0.05  # Simplified p-value
            else:
                slope, r_value, p_value = 0, 0, 1

            # Determine trend direction and strength
            if slope > 0.1:
                trend_direction = "improving"
            elif slope < -0.1:
                trend_direction = "declining"
            else:
                trend_direction = "stable"

            # Calculate weekly patterns
            df["day_of_week"] = df["timestamp"].dt.day_name()
            weekly_pattern = df.groupby("day_of_week")["mood_score"].mean().to_dict()

            # Calculate hourly patterns if we have enough data
            hourly_pattern = {}
            if len(df) > 10:
                df["hour"] = df["timestamp"].dt.hour
                hourly_pattern = df.groupby("hour")["mood_score"].mean().to_dict()

            return {
                "trend_direction": trend_direction,
                "trend_strength": abs(float(slope)),
                "trend_significance": float(1 - p_value) if p_value < 1 else 0.0,
                "correlation_coefficient": float(r_value) if r_value else 0.0,
                "daily_averages": daily_moods.set_index("date")["mean"].to_dict(),
                "weekly_pattern": weekly_pattern,
                "hourly_pattern": hourly_pattern,
                "volatility": float(daily_moods["mean"].std())
                if len(daily_moods) > 1
                else 0.0,
            }

        except Exception as exc:
            logger.error(f"Error analyzing mood trends: {str(exc)}")
            return {}

    def _analyze_activity_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze activity patterns and their relationship to mood"""
        try:
            if df.empty or "activities" not in df:
                return {}

            # Extract all activities
            all_activities = []
            activity_mood_map = {}

            for idx, row in df.iterrows():
                activities = row.get("activities", [])
                mood_score = row.get("mood_score")

                if isinstance(activities, list) and mood_score is not None:
                    for activity in activities:
                        all_activities.append(activity)
                        if activity not in activity_mood_map:
                            activity_mood_map[activity] = []
                        activity_mood_map[activity].append(mood_score)

            if not all_activities:
                return {}

            # Calculate activity statistics
            activity_counts = pd.Series(all_activities).value_counts()

            # Calculate average mood for each activity
            activity_mood_averages = {}
            for activity, moods in activity_mood_map.items():
                if moods:
                    activity_mood_averages[activity] = {
                        "average_mood": np.mean(moods),
                        "mood_count": len(moods),
                        "mood_std": np.std(moods) if len(moods) > 1 else 0.0,
                    }

            return {
                "total_activities_logged": len(all_activities),
                "unique_activities": len(set(all_activities)),
                "activity_frequency": activity_counts.head(10).to_dict(),
                "activity_mood_correlation": activity_mood_averages,
                "most_positive_activities": sorted(
                    activity_mood_averages.items(),
                    key=lambda x: x[1]["average_mood"],
                    reverse=True,
                )[:5],
                "activity_diversity_score": len(set(all_activities))
                / len(all_activities)
                if all_activities
                else 0,
            }

        except Exception as exc:
            logger.error(f"Error analyzing activity patterns: {str(exc)}")
            return {}

    def _analyze_sleep_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sleep patterns and their impact on mood"""
        try:
            if df.empty or "sleep_hours" not in df:
                return {}

            sleep_data = df[df["sleep_hours"].notna()]

            if sleep_data.empty:
                return {}

            sleep_hours = sleep_data["sleep_hours"]
            mood_scores = sleep_data["mood_score"]

            # Calculate sleep statistics
            sleep_stats = {
                "average_sleep": float(sleep_hours.mean()),
                "median_sleep": float(sleep_hours.median()),
                "min_sleep": float(sleep_hours.min()),
                "max_sleep": float(sleep_hours.max()),
                "sleep_consistency": float(sleep_hours.std())
                if len(sleep_hours) > 1
                else 0.0,
                "optimal_sleep_range": [7, 9],  # Standard recommendation
            }

            # Analyze sleep-mood correlation
            if len(sleep_data) > 5:
                correlation = (
                    np.corrcoef(sleep_hours, mood_scores)[0, 1]
                    if len(sleep_hours) > 1
                    else 0
                )
                sleep_stats["sleep_mood_correlation"] = (
                    float(correlation) if not np.isnan(correlation) else 0.0
                )

                # Categorize sleep quality impact
                if sleep_stats["sleep_mood_correlation"] > 0.3:
                    sleep_stats["sleep_impact"] = "strong_positive"
                elif sleep_stats["sleep_mood_correlation"] > 0.1:
                    sleep_stats["sleep_impact"] = "moderate_positive"
                elif sleep_stats["sleep_mood_correlation"] < -0.3:
                    sleep_stats["sleep_impact"] = "strong_negative"
                elif sleep_stats["sleep_mood_correlation"] < -0.1:
                    sleep_stats["sleep_impact"] = "moderate_negative"
                else:
                    sleep_stats["sleep_impact"] = "minimal"

            # Sleep quality categorization
            avg_sleep = sleep_stats["average_sleep"]
            if 7 <= avg_sleep <= 9:
                sleep_stats["sleep_quality_category"] = "optimal"
            elif 6 <= avg_sleep < 7 or 9 < avg_sleep <= 10:
                sleep_stats["sleep_quality_category"] = "adequate"
            else:
                sleep_stats["sleep_quality_category"] = "concerning"

            return sleep_stats

        except Exception as exc:
            logger.error(f"Error analyzing sleep patterns: {str(exc)}")
            return {}

    def _analyze_energy_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze energy level patterns"""
        try:
            if df.empty or "energy_level" not in df:
                return {}

            energy_data = df[df["energy_level"].notna()]

            if energy_data.empty:
                return {}

            energy_levels = energy_data["energy_level"]
            mood_scores = energy_data["mood_score"]

            energy_stats = {
                "average_energy": float(energy_levels.mean()),
                "median_energy": float(energy_levels.median()),
                "min_energy": float(energy_levels.min()),
                "max_energy": float(energy_levels.max()),
                "energy_consistency": float(energy_levels.std())
                if len(energy_levels) > 1
                else 0.0,
                "energy_distribution": energy_levels.value_counts().to_dict(),
            }

            # Energy-mood correlation
            if len(energy_data) > 5:
                correlation = (
                    np.corrcoef(energy_levels, mood_scores)[0, 1]
                    if len(energy_levels) > 1
                    else 0
                )
                energy_stats["energy_mood_correlation"] = (
                    float(correlation) if not np.isnan(correlation) else 0.0
                )

            # Energy trend analysis
            if len(energy_data) > 2:
                x = np.arange(len(energy_levels))
                slope = np.polyfit(x, energy_levels, 1)[0]

                if slope > 0.1:
                    energy_stats["energy_trend"] = "increasing"
                elif slope < -0.1:
                    energy_stats["energy_trend"] = "decreasing"
                else:
                    energy_stats["energy_trend"] = "stable"

            return energy_stats

        except Exception as exc:
            logger.error(f"Error analyzing energy patterns: {str(exc)}")
            return {}

    def _analyze_stress_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze stress level patterns"""
        try:
            if df.empty or "stress_level" not in df:
                return {}

            stress_data = df[df["stress_level"].notna()]

            if stress_data.empty:
                return {}

            stress_levels = stress_data["stress_level"]
            mood_scores = stress_data["mood_score"]

            stress_stats = {
                "average_stress": float(stress_levels.mean()),
                "median_stress": float(stress_levels.median()),
                "max_stress": float(stress_levels.max()),
                "min_stress": float(stress_levels.min()),
                "stress_variability": float(stress_levels.std())
                if len(stress_levels) > 1
                else 0.0,
                "stress_distribution": stress_levels.value_counts().to_dict(),
            }

            # Stress-mood correlation (should be negative)
            if len(stress_data) > 5:
                correlation = (
                    np.corrcoef(stress_levels, mood_scores)[0, 1]
                    if len(stress_levels) > 1
                    else 0
                )
                stress_stats["stress_mood_correlation"] = (
                    float(correlation) if not np.isnan(correlation) else 0.0
                )

            # Stress level categorization
            avg_stress = stress_stats["average_stress"]
            if avg_stress <= 3:
                stress_stats["stress_category"] = "low"
            elif avg_stress <= 6:
                stress_stats["stress_category"] = "moderate"
            else:
                stress_stats["stress_category"] = "high"

            # High stress day identification
            high_stress_threshold = 7
            high_stress_days = len(
                stress_data[stress_data["stress_level"] >= high_stress_threshold]
            )
            stress_stats["high_stress_days"] = high_stress_days
            stress_stats["high_stress_percentage"] = (
                (high_stress_days / len(stress_data)) * 100
                if len(stress_data) > 0
                else 0
            )

            return stress_stats

        except Exception as exc:
            logger.error(f"Error analyzing stress patterns: {str(exc)}")
            return {}

    def _get_empty_mood_statistics(self) -> Dict[str, Any]:
        """Return empty mood statistics structure"""
        return {
            "count": 0,
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "std_deviation": 0.0,
            "variance": 0.0,
            "range": 0.0,
            "mood_distribution": {},
            "percentiles": {"25th": None, "75th": None, "90th": None},
            "overall_mood_category": "insufficient_data",
        }

    def _update_performance_metrics(self, start_time: float, records_processed: int):
        """Update performance tracking metrics"""
        import time

        try:
            self.collection_stats["total_collections"] += 1

            collection_time = time.time() - start_time
            total_collections = self.collection_stats["total_collections"]

            # Update average collection time
            current_avg = self.collection_stats["avg_collection_time"]
            new_avg = (
                (current_avg * (total_collections - 1)) + collection_time
            ) / total_collections
            self.collection_stats["avg_collection_time"] = new_avg

        except Exception:
            pass  # Don't let metrics update failure affect the main process

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.collection_stats.copy()

    def clear_cache(self, user_id: Optional[int] = None):
        """Clear cache for specific user or all mood data cache"""
        if user_id:
            for days in [7, 14, 30, 60, 90]:
                cache_key = f"mood_data:{user_id}:{days}"
                cache.delete(cache_key)
        else:
            # Clear all mood-related cache keys
            cache.delete_many(
                [key for key in cache.keys() if key.startswith("mood_data:")]
            )


# Create singleton instance
mood_tracking_service = MoodTrackingCollectionService()

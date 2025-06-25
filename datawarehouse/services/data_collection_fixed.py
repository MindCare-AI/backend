# datawarehouse/services/data_collection.py
"""
Enterprise-Grade Centralized Data Collection Service for MindCare AI Engine
Uses modern Python tools for high-performance data processing
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.cache import cache
import pandas as pd
import numpy as np
import logging
import structlog
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from pydantic import BaseModel, Field, validator

try:
    import polars as pl
except ImportError:
    pl = None


# Configure structured logging
logger = structlog.get_logger(__name__)
django_logger = logging.getLogger(__name__)

User = get_user_model()


class DataCollectionConfig(BaseModel):
    """Configuration for data collection with validation"""

    cache_timeout: int = Field(default=900, ge=60, le=3600)
    max_workers: int = Field(default=4, ge=1, le=10)
    batch_size: int = Field(default=1000, ge=100, le=5000)
    quality_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    @validator("max_workers")
    def validate_workers(cls, v):
        if v > 8:
            logger.warning("High worker count may impact performance", workers=v)
        return v


@dataclass
class DataCollectionMetrics:
    """Metrics for data collection performance"""

    collection_time: float
    records_collected: int
    data_sources: List[str]
    quality_score: float
    errors: List[str]
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class UserDataSnapshot:
    """Structured representation of user data"""

    user_id: int
    collection_date: datetime
    period_days: int
    mood_data: Dict[str, Any]
    journal_data: Dict[str, Any]
    messaging_data: Dict[str, Any]
    appointment_data: Dict[str, Any]
    notification_data: Dict[str, Any]
    analytics_data: Dict[str, Any]
    social_data: Dict[str, Any]
    metadata: Dict[str, Any]


class DataCollectionService:
    """
    Enterprise-grade data collection service using modern Python tools

    Features:
    - Pandas/Polars for high-performance data processing
    - Async data collection from multiple sources
    - Comprehensive error handling and validation
    - Performance monitoring and caching
    - Structured logging with structlog
    - Pydantic validation for data integrity
    """

    def __init__(self, config: Optional[DataCollectionConfig] = None):
        self.config = config or DataCollectionConfig()
        self.performance_metrics = {}

        # Performance tracking
        self.collection_stats = {
            "total_collections": 0,
            "avg_collection_time": 0.0,
            "error_rate": 0.0,
            "cache_hit_rate": 0.0,
        }

    def collect_user_data(self, user_id: int, days: int = 30) -> UserDataSnapshot:
        """
        Main entry point for collecting user data

        Args:
            user_id: User identifier
            days: Number of days to collect data for

        Returns:
            UserDataSnapshot with all collected data
        """
        start_time = time.time()
        logger.info("Starting data collection", user_id=user_id, days=days)

        try:
            # Validate inputs
            if days <= 0 or days > 365:
                raise ValueError(f"Invalid days parameter: {days}")

            # Check cache first
            cache_key = f"user_data:{user_id}:{days}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info("Returning cached data", user_id=user_id)
                self.collection_stats["cache_hit_rate"] += 1
                return UserDataSnapshot(**cached_data)

            # Get user object
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError(f"User {user_id} not found")

            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Collect data from all sources
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                # Submit all collection tasks
                futures = {
                    executor.submit(
                        self._collect_mood_data, user, start_date, end_date
                    ): "mood",
                    executor.submit(
                        self._collect_journal_data, user, start_date, end_date
                    ): "journal",
                    executor.submit(
                        self._collect_messaging_data, user, start_date, end_date
                    ): "messaging",
                    executor.submit(
                        self._collect_appointment_data, user, start_date, end_date
                    ): "appointment",
                    executor.submit(
                        self._collect_notification_data, user, start_date, end_date
                    ): "notification",
                    executor.submit(
                        self._collect_analytics_data, user, start_date, end_date
                    ): "analytics",
                    executor.submit(
                        self._collect_social_data, user, start_date, end_date
                    ): "social",
                }

                # Collect results
                results = {}
                errors = []

                for future in as_completed(futures):
                    data_type = futures[future]
                    try:
                        results[f"{data_type}_data"] = future.result()
                    except Exception as exc:
                        logger.error(
                            f"Error collecting {data_type} data", error=str(exc)
                        )
                        errors.append(f"{data_type}: {str(exc)}")
                        results[f"{data_type}_data"] = {}

            # Create snapshot
            snapshot = UserDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                mood_data=results.get("mood_data", {}),
                journal_data=results.get("journal_data", {}),
                messaging_data=results.get("messaging_data", {}),
                appointment_data=results.get("appointment_data", {}),
                notification_data=results.get("notification_data", {}),
                analytics_data=results.get("analytics_data", {}),
                social_data=results.get("social_data", {}),
                metadata={
                    "collection_time": time.time() - start_time,
                    "errors": errors,
                    "data_sources": list(results.keys()),
                    "version": "2.0",
                },
            )

            # Cache the results
            cache.set(cache_key, asdict(snapshot), self.config.cache_timeout)

            # Update performance metrics
            self._update_performance_metrics(start_time, len(results), errors)

            logger.info(
                "Data collection completed",
                user_id=user_id,
                collection_time=time.time() - start_time,
                data_sources=len(results),
            )

            return snapshot

        except Exception as exc:
            logger.error("Data collection failed", user_id=user_id, error=str(exc))
            raise

    def _collect_mood_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect and process mood data using pandas for efficiency"""
        try:
            # Import here to avoid circular imports
            from mood.models import MoodLog

            # Get mood logs
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
                return {
                    "count": 0,
                    "avg_mood": None,
                    "trend": "stable",
                    "volatility": 0.0,
                    "entries": [],
                }

            # Convert to pandas DataFrame for analysis
            df = pd.DataFrame(list(mood_logs))
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            # Calculate statistics
            mood_scores = df["mood_score"].dropna()

            analysis = {
                "count": len(df),
                "avg_mood": float(mood_scores.mean())
                if not mood_scores.empty
                else None,
                "min_mood": float(mood_scores.min()) if not mood_scores.empty else None,
                "max_mood": float(mood_scores.max()) if not mood_scores.empty else None,
                "volatility": float(mood_scores.std()) if len(mood_scores) > 1 else 0.0,
                "trend": self._calculate_trend(mood_scores.values),
                "daily_averages": self._calculate_daily_averages(df),
                "activity_patterns": self._analyze_activity_patterns(df),
                "entries": df.to_dict("records"),
            }

            return analysis

        except Exception as exc:
            logger.error("Error collecting mood data", error=str(exc))
            return {"error": str(exc), "count": 0, "entries": []}

    def _collect_journal_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect and analyze journal data"""
        try:
            from journal.models import JournalEntry

            entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).values(
                "id",
                "title",
                "content",
                "mood_before",
                "mood_after",
                "created_at",
                "category_id",
                "tags",
            )

            if not entries:
                return {
                    "count": 0,
                    "sentiment_trend": "neutral",
                    "topics": [],
                    "entries": [],
                }

            # Convert to DataFrame
            df = pd.DataFrame(list(entries))

            # Analyze content
            analysis = {
                "count": len(df),
                "avg_content_length": df["content"].str.len().mean(),
                "mood_improvement": self._calculate_mood_improvement(df),
                "sentiment_analysis": self._analyze_journal_sentiment(df),
                "topic_analysis": self._extract_journal_topics(df),
                "writing_frequency": self._analyze_writing_frequency(df),
                "entries": df.to_dict("records"),
            }

            return analysis

        except Exception as exc:
            logger.error("Error collecting journal data", error=str(exc))
            return {"error": str(exc), "count": 0, "entries": []}

    def _collect_messaging_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect messaging data for communication pattern analysis"""
        try:
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage

            # Get one-to-one messages
            one_to_one_msgs = OneToOneMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date),
            ).values("id", "content", "timestamp", "sender_id", "conversation_id")

            # Get group messages
            group_msgs = GroupMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date),
            ).values("id", "content", "timestamp", "sender_id", "conversation_id")

            # Combine and analyze
            one_to_one_df = pd.DataFrame(list(one_to_one_msgs))
            group_df = pd.DataFrame(list(group_msgs))

            communication_stats = self._analyze_communication_patterns(
                one_to_one_df, group_df
            )

            return {
                "one_to_one_messages": one_to_one_df.to_dict("records")
                if not one_to_one_df.empty
                else [],
                "group_messages": group_df.to_dict("records")
                if not group_df.empty
                else [],
                "statistics": communication_stats,
                "data_quality": {
                    "message_completeness": (len(one_to_one_df) + len(group_df))
                    / max(1, (end_date - start_date).days)
                },
            }

        except Exception as exc:
            logger.error("Messaging data collection failed", error=str(exc))
            return self._get_empty_messaging_data()

    def _collect_appointment_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect appointment data"""
        try:
            from appointments.models import Appointment

            appointments = Appointment.objects.filter(
                Q(patient=user) | Q(therapist=user),
                scheduled_time__range=(start_date, end_date),
            ).values(
                "id",
                "scheduled_time",
                "status",
                "duration",
                "appointment_type",
                "notes",
            )

            df = pd.DataFrame(list(appointments))

            if df.empty:
                return self._get_empty_appointment_data()

            appointment_stats = {
                "total_appointments": len(df),
                "completed_appointments": len(df[df["status"] == "completed"])
                if "status" in df
                else 0,
                "cancelled_appointments": len(df[df["status"] == "cancelled"])
                if "status" in df
                else 0,
                "avg_duration": df["duration"].mean() if "duration" in df else 0,
                "appointment_frequency": len(df)
                / max(1, (end_date - start_date).days / 7),  # per week
            }

            return {
                "records": df.to_dict("records"),
                "statistics": appointment_stats,
                "data_quality": {
                    "appointment_regularity": appointment_stats["appointment_frequency"]
                },
            }

        except Exception as exc:
            logger.error("Appointment data collection failed", error=str(exc))
            return self._get_empty_appointment_data()

    def _collect_notification_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect notification interaction data"""
        try:
            from notifications.models import Notification

            notifications = Notification.objects.filter(
                recipient=user, timestamp__range=(start_date, end_date)
            ).values("id", "verb", "level", "timestamp", "unread", "data")

            df = pd.DataFrame(list(notifications))

            if df.empty:
                return self._get_empty_notification_data()

            notification_stats = {
                "total_notifications": len(df),
                "unread_notifications": len(df[df["unread"]])
                if "unread" in df
                else 0,
                "read_rate": 1 - (len(df[df["unread"]]) / len(df))
                if "unread" in df and len(df) > 0
                else 0,
                "notification_types": df["verb"].value_counts().to_dict()
                if "verb" in df
                else {},
            }

            return {
                "records": df.to_dict("records"),
                "statistics": notification_stats,
                "data_quality": {"engagement_rate": notification_stats["read_rate"]},
            }

        except Exception as exc:
            logger.error("Notification data collection failed", error=str(exc))
            return self._get_empty_notification_data()

    def _collect_analytics_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect analytics and usage data"""
        try:
            # This would integrate with analytics models when available
            # For now, return basic structure
            return {
                "usage_stats": {
                    "login_count": 0,
                    "session_duration": 0,
                    "feature_usage": {},
                },
                "data_quality": {"tracking_completeness": 0.5},
            }

        except Exception as exc:
            logger.error("Analytics data collection failed", error=str(exc))
            return {"usage_stats": {}, "data_quality": {"tracking_completeness": 0}}

    def _collect_social_data(
        self, user, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect social interaction data from feeds"""
        try:
            from feeds.models import Post, Comment, Like

            # Get user's posts
            posts = Post.objects.filter(
                creator=user, created_at__range=(start_date, end_date)
            ).values("id", "content", "created_at", "is_anonymous")

            # Get user's comments
            comments = Comment.objects.filter(
                creator=user, created_at__range=(start_date, end_date)
            ).values("id", "content", "created_at", "post_id")

            # Get user's likes
            likes = Like.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).values("id", "created_at", "post_id")

            # Convert to DataFrames
            posts_df = pd.DataFrame(list(posts))
            comments_df = pd.DataFrame(list(comments))
            likes_df = pd.DataFrame(list(likes))

            # Calculate social engagement metrics
            social_stats = {
                "posts_created": len(posts_df),
                "comments_made": len(comments_df),
                "likes_given": len(likes_df),
                "social_engagement_score": self._calculate_social_engagement(
                    posts_df, comments_df, likes_df
                ),
            }

            return {
                "posts": posts_df.to_dict("records") if not posts_df.empty else [],
                "comments": comments_df.to_dict("records")
                if not comments_df.empty
                else [],
                "likes": likes_df.to_dict("records") if not likes_df.empty else [],
                "statistics": social_stats,
                "data_quality": {
                    "social_activity_level": social_stats["social_engagement_score"]
                },
            }

        except Exception as exc:
            logger.error("Social data collection failed", error=str(exc))
            return self._get_empty_social_data()

    # Helper methods for data analysis
    def _calculate_trend(self, values) -> str:
        """Calculate trend direction from values"""
        try:
            if len(values) < 2:
                return "stable"

            # Simple linear regression to determine trend
            x = np.arange(len(values))
            slope, _ = np.polyfit(x, values, 1)

            if slope > 0.1:
                return "improving"
            elif slope < -0.1:
                return "declining"
            else:
                return "stable"

        except Exception:
            return "stable"

    def _calculate_daily_averages(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate daily averages from mood data"""
        try:
            if df.empty or "timestamp" not in df or "mood_score" not in df:
                return {}

            df["date"] = df["timestamp"].dt.date
            daily_avg = df.groupby("date")["mood_score"].mean()
            return daily_avg.to_dict()

        except Exception:
            return {}

    def _analyze_activity_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze activity patterns from mood data"""
        try:
            if df.empty or "activities" not in df:
                return {}

            # Extract and count activities
            all_activities = []
            for activities in df["activities"].dropna():
                if isinstance(activities, list):
                    all_activities.extend(activities)

            if not all_activities:
                return {}

            activity_counts = pd.Series(all_activities).value_counts()

            return {
                "total_activities": len(all_activities),
                "unique_activities": len(set(all_activities)),
                "top_activities": activity_counts.head(5).to_dict(),
                "activity_frequency": len(all_activities) / len(df)
                if len(df) > 0
                else 0,
            }

        except Exception:
            return {}

    def _calculate_mood_improvement(self, df: pd.DataFrame) -> float:
        """Calculate mood improvement from journal entries"""
        try:
            if df.empty or "mood_before" not in df or "mood_after" not in df:
                return 0.0

            before_mood = df["mood_before"].dropna().mean()
            after_mood = df["mood_after"].dropna().mean()

            if pd.isna(before_mood) or pd.isna(after_mood):
                return 0.0

            return float(after_mood - before_mood)

        except Exception:
            return 0.0

    def _analyze_journal_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sentiment in journal entries"""
        try:
            if df.empty or "content" not in df:
                return {}

            # Basic sentiment analysis - could be enhanced with NLP libraries
            positive_words = [
                "happy",
                "good",
                "great",
                "wonderful",
                "joy",
                "excited",
                "grateful",
            ]
            negative_words = [
                "sad",
                "bad",
                "terrible",
                "awful",
                "angry",
                "frustrated",
                "worried",
            ]

            sentiment_scores = []
            for content in df["content"].dropna():
                content_lower = content.lower()
                positive_count = sum(
                    1 for word in positive_words if word in content_lower
                )
                negative_count = sum(
                    1 for word in negative_words if word in content_lower
                )

                if positive_count + negative_count > 0:
                    sentiment = (positive_count - negative_count) / (
                        positive_count + negative_count
                    )
                else:
                    sentiment = 0

                sentiment_scores.append(sentiment)

            if sentiment_scores:
                avg_sentiment = np.mean(sentiment_scores)
                if avg_sentiment > 0.1:
                    trend = "positive"
                elif avg_sentiment < -0.1:
                    trend = "negative"
                else:
                    trend = "neutral"
            else:
                avg_sentiment = 0
                trend = "neutral"

            return {
                "average_sentiment": float(avg_sentiment),
                "sentiment_trend": trend,
                "sentiment_scores": sentiment_scores,
            }

        except Exception:
            return {}

    def _extract_journal_topics(self, df: pd.DataFrame) -> List[str]:
        """Extract topics from journal entries"""
        try:
            if df.empty or "content" not in df:
                return []

            # Simple keyword extraction - could be enhanced with NLP
            common_topics = [
                "work",
                "family",
                "friends",
                "health",
                "exercise",
                "sleep",
                "therapy",
                "medication",
            ]
            found_topics = []

            for content in df["content"].dropna():
                content_lower = content.lower()
                for topic in common_topics:
                    if topic in content_lower and topic not in found_topics:
                        found_topics.append(topic)

            return found_topics

        except Exception:
            return []

    def _analyze_writing_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze writing frequency patterns"""
        try:
            if df.empty or "created_at" not in df:
                return {}

            df["date"] = pd.to_datetime(df["created_at"]).dt.date
            daily_counts = df.groupby("date").size()

            return {
                "avg_entries_per_day": float(daily_counts.mean()),
                "max_entries_per_day": int(daily_counts.max()),
                "total_writing_days": len(daily_counts),
                "writing_consistency": float(daily_counts.std())
                if len(daily_counts) > 1
                else 0.0,
            }

        except Exception:
            return {}

    def _analyze_communication_patterns(
        self, one_to_one_df: pd.DataFrame, group_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze communication patterns"""
        try:
            stats = {
                "one_to_one_messages": len(one_to_one_df),
                "group_messages": len(group_df),
                "total_messages": len(one_to_one_df) + len(group_df),
                "message_ratio": len(one_to_one_df) / max(1, len(group_df))
                if len(group_df) > 0
                else len(one_to_one_df),
            }

            # Analyze timing patterns if data is available
            combined_df = pd.concat([one_to_one_df, group_df], ignore_index=True)
            if not combined_df.empty and "timestamp" in combined_df:
                combined_df["hour"] = pd.to_datetime(combined_df["timestamp"]).dt.hour
                stats["most_active_hour"] = (
                    int(combined_df["hour"].mode().iloc[0])
                    if not combined_df["hour"].mode().empty
                    else None
                )
                stats["hourly_distribution"] = (
                    combined_df["hour"].value_counts().to_dict()
                )

            return stats

        except Exception:
            return {"one_to_one_messages": 0, "group_messages": 0, "total_messages": 0}

    def _calculate_social_engagement(
        self, posts_df: pd.DataFrame, comments_df: pd.DataFrame, likes_df: pd.DataFrame
    ) -> float:
        """Calculate social engagement score"""
        try:
            # Simple engagement score based on activity
            posts_weight = 3
            comments_weight = 2
            likes_weight = 1

            score = (
                len(posts_df) * posts_weight
                + len(comments_df) * comments_weight
                + len(likes_df) * likes_weight
            )

            # Normalize to 0-1 scale (assuming max engagement per day is 10)
            max_daily_engagement = 10
            days = 30  # Default period
            max_score = max_daily_engagement * days * posts_weight

            return min(1.0, score / max_score)

        except Exception:
            return 0.0

    def _update_performance_metrics(
        self, start_time: float, data_sources_count: int, errors: List[str]
    ):
        """Update performance tracking metrics"""
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

            # Update error rate
            if errors:
                self.collection_stats["error_rate"] += 1

        except Exception:
            pass  # Don't let metrics update failure affect the main process

    # Empty data structure methods
    def _get_empty_messaging_data(self) -> Dict[str, Any]:
        return {
            "one_to_one_messages": [],
            "group_messages": [],
            "statistics": {
                "one_to_one_messages": 0,
                "group_messages": 0,
                "total_messages": 0,
            },
            "data_quality": {"message_completeness": 0},
        }

    def _get_empty_appointment_data(self) -> Dict[str, Any]:
        return {
            "records": [],
            "statistics": {"total_appointments": 0, "appointment_frequency": 0},
            "data_quality": {"appointment_regularity": 0},
        }

    def _get_empty_notification_data(self) -> Dict[str, Any]:
        return {
            "records": [],
            "statistics": {"total_notifications": 0, "read_rate": 0},
            "data_quality": {"engagement_rate": 0},
        }

    def _get_empty_social_data(self) -> Dict[str, Any]:
        return {
            "posts": [],
            "comments": [],
            "likes": [],
            "statistics": {"social_engagement_score": 0},
            "data_quality": {"social_activity_level": 0},
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.collection_stats.copy()

    def clear_cache(self, user_id: Optional[int] = None):
        """Clear cache for specific user or all users"""
        if user_id:
            # Clear specific user cache patterns
            for days in [7, 14, 30, 60, 90]:
                cache_key = f"user_data:{user_id}:{days}"
                cache.delete(cache_key)
        else:
            cache.clear()


# Create singleton instance
data_collector = DataCollectionService()

# AI_engine/services/tips_service.py
from typing import Dict, List, Any
import logging
import numpy as np
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from collections import defaultdict

logger = logging.getLogger(__name__)


class TipsService:
    """Service for generating personalized tips based on mood and journal analysis"""

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

    def generate_mood_tips(
        self, user, days: int = 7, tip_count: int = 5
    ) -> Dict[str, Any]:
        """Generate personalized tips based on mood tracking data using AI data interface"""
        cache_key = f"mood_tips_{user.id}_{days}_{tip_count}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Import AI data interface service
            from .data_interface import ai_data_interface

            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, days)

            # Check data quality and availability
            quality_metrics = dataset.get("quality_metrics", {})
            if quality_metrics.get("overall_quality", 0.0) < 0.1:
                logger.warning(
                    f"Insufficient data quality for user {user.id} mood tips: {quality_metrics}"
                )
                return self._create_default_mood_tips()

            # Extract mood data from AI-ready dataset
            mood_data = self._extract_mood_data_from_dataset(dataset)

            if not mood_data["mood_logs"]:
                return self._create_default_mood_tips()

            # Analyze mood patterns
            mood_analysis = self._analyze_mood_patterns(mood_data)

            # Generate tips using AI
            tips = self._generate_ai_mood_tips(mood_analysis, tip_count)

            # Format response with datawarehouse integration metrics
            result = {
                "tips": tips,
                "mood_analysis": mood_analysis,
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": len(tips),
                "data_integration": {
                    "data_sources_used": dataset.get("data_sources", []),
                    "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                    "completeness_score": quality_metrics.get("completeness", 0.0),
                    "analysis_recommendation": quality_metrics.get(
                        "analysis_recommendation", "unknown"
                    ),
                    "datawarehouse_version": dataset.get("processing_metadata", {}).get(
                        "processing_version", "unknown"
                    ),
                },
            }

            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)
            return result

        except Exception as e:
            logger.error(
                f"Error generating mood tips with AI data interface: {str(e)}",
                exc_info=True,
            )
            return self._create_default_mood_tips()

    def generate_journaling_tips(
        self, user, days: int = 14, tip_count: int = 5
    ) -> Dict[str, Any]:
        """Generate personalized tips based on journal analysis using AI data interface"""
        cache_key = f"journal_tips_{user.id}_{days}_{tip_count}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Import AI data interface service
            from .data_interface import ai_data_interface

            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, days)

            # Check data quality and availability
            quality_metrics = dataset.get("quality_metrics", {})
            if quality_metrics.get("overall_quality", 0.0) < 0.1:
                logger.warning(
                    f"Insufficient data quality for user {user.id} journal tips: {quality_metrics}"
                )
                return self._create_default_journaling_tips()

            # Extract journal data from AI-ready dataset
            journal_data = self._extract_journal_data_from_dataset(dataset)

            if not journal_data["journal_entries"]:
                return self._create_default_journaling_tips()

            # Analyze journal patterns
            journal_analysis = self._analyze_journal_patterns(journal_data)

            # Generate tips using AI
            tips = self._generate_ai_journal_tips(journal_analysis, tip_count)

            # Format response with datawarehouse integration metrics
            result = {
                "tips": tips,
                "journal_analysis": journal_analysis,
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": len(tips),
                "data_integration": {
                    "data_sources_used": dataset.get("data_sources", []),
                    "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                    "completeness_score": quality_metrics.get("completeness", 0.0),
                    "analysis_recommendation": quality_metrics.get(
                        "analysis_recommendation", "unknown"
                    ),
                    "datawarehouse_version": dataset.get("processing_metadata", {}).get(
                        "processing_version", "unknown"
                    ),
                },
            }

            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)
            return result

        except Exception as e:
            logger.error(
                f"Error generating journal tips with AI data interface: {str(e)}",
                exc_info=True,
            )
            return self._create_default_journaling_tips()

    def generate_combined_tips(
        self, user, days: int = 14, tip_count: int = 8
    ) -> Dict[str, Any]:
        """Generate comprehensive tips based on both mood and journal data"""
        cache_key = f"combined_tips_{user.id}_{days}_{tip_count}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Collect both mood and journal data
            mood_data = self._collect_mood_data(user, days)
            journal_data = self._collect_journal_data(user, days)

            # Analyze patterns
            mood_analysis = self._analyze_mood_patterns(mood_data)
            journal_analysis = self._analyze_journal_patterns(journal_data)

            # Combine analyses
            combined_analysis = self._combine_analyses(mood_analysis, journal_analysis)

            # Generate comprehensive tips
            tips = self._generate_ai_combined_tips(combined_analysis, tip_count)

            # Format response
            result = {
                "tips": tips,
                "mood_analysis": mood_analysis,
                "journal_analysis": journal_analysis,
                "combined_insights": combined_analysis,
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": len(tips),
            }

            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)
            return result

        except Exception as e:
            logger.error(f"Error generating combined tips: {str(e)}", exc_info=True)
            return self._create_default_combined_tips()

    def _extract_mood_data_from_dataset(self, dataset: Dict) -> Dict[str, Any]:
        """Extract mood data from AI-ready dataset in format expected by existing analysis methods"""
        try:
            mood_analytics = dataset.get("mood_analytics", {})

            # Convert AI-ready format to expected format
            mood_logs = []
            daily_patterns = defaultdict(list)
            weekly_patterns = defaultdict(list)
            activity_patterns = defaultdict(list)
            note_keywords = defaultdict(int)

            # Extract mood entries from analytics if available
            if mood_analytics.get("mood_entries"):
                for entry in mood_analytics["mood_entries"]:
                    mood_entry = {
                        "rating": entry.get("rating", entry.get("mood_rating", 5)),
                        "activities": entry.get("activities", []),
                        "notes": entry.get("notes", ""),
                        "logged_at": entry.get("logged_at", entry.get("timestamp", "")),
                        "day_of_week": entry.get("day_of_week", 0),
                        "hour_of_day": entry.get("hour_of_day", 12),
                        "date": entry.get("date", ""),
                        "week_of_year": entry.get("week_of_year", 1),
                        "is_weekend": entry.get("is_weekend", False),
                        "time_of_day": entry.get("time_of_day", "afternoon"),
                    }
                    mood_logs.append(mood_entry)

                    # Build patterns for analysis
                    if mood_entry["date"]:
                        daily_patterns[mood_entry["date"]].append(mood_entry["rating"])
                    weekly_patterns[mood_entry["day_of_week"]].append(
                        mood_entry["rating"]
                    )

                    for activity in mood_entry["activities"]:
                        activity_patterns[activity].append(
                            {
                                "mood": mood_entry["rating"],
                                "time": mood_entry["hour_of_day"],
                                "day": mood_entry["day_of_week"],
                            }
                        )

                    # Extract keywords from notes
                    if mood_entry["notes"]:
                        keywords = self._extract_mood_keywords(
                            mood_entry["notes"].lower()
                        )
                        for keyword in keywords:
                            note_keywords[keyword] += 1

            # Calculate advanced metrics using available data
            mood_volatility = (
                self._calculate_detailed_volatility(mood_logs) if mood_logs else {}
            )
            activity_effectiveness = (
                self._analyze_activity_effectiveness(activity_patterns)
                if activity_patterns
                else {}
            )
            temporal_insights = (
                self._analyze_detailed_temporal_patterns(mood_logs) if mood_logs else {}
            )
            stress_indicators = (
                self._identify_stress_patterns(mood_logs, note_keywords)
                if mood_logs
                else {}
            )

            return {
                "mood_logs": mood_logs,
                "total_logs": len(mood_logs),
                "date_range": dataset.get("processing_metadata", {}).get(
                    "date_range", {}
                ),
                "daily_patterns": dict(daily_patterns),
                "weekly_patterns": dict(weekly_patterns),
                "activity_patterns": dict(activity_patterns),
                "note_keywords": dict(note_keywords),
                "mood_volatility": mood_volatility,
                "activity_effectiveness": activity_effectiveness,
                "temporal_insights": temporal_insights,
                "stress_indicators": stress_indicators,
            }

        except Exception as e:
            logger.error(f"Error extracting mood data from dataset: {str(e)}")
            return {"mood_logs": [], "total_logs": 0, "date_range": {}}

    def _extract_journal_data_from_dataset(self, dataset: Dict) -> Dict[str, Any]:
        """Extract journal data from AI-ready dataset in format expected by existing analysis methods"""
        try:
            journal_analytics = dataset.get("journal_analytics", {})

            # Convert AI-ready format to expected format
            journal_entries = []
            emotional_keywords = defaultdict(int)
            topic_clusters = defaultdict(list)
            writing_quality_metrics = []
            sentiment_evolution = []

            # Extract journal entries from analytics if available
            if journal_analytics.get("journal_entries"):
                for entry in journal_analytics["journal_entries"]:
                    entry_data = {
                        "content": entry.get("content", "")[:500],  # Limit for analysis
                        "full_content_length": len(entry.get("content", "")),
                        "word_count": entry.get("word_count", 0),
                        "sentence_count": entry.get("sentence_count", 0),
                        "mood": entry.get("mood", "neutral"),
                        "activities": entry.get("activities", []),
                        "created_at": entry.get(
                            "created_at", entry.get("timestamp", "")
                        ),
                        "day_of_week": entry.get("day_of_week", 0),
                        "hour_of_day": entry.get("hour_of_day", 12),
                        "date": entry.get("date", ""),
                        "is_weekend": entry.get("is_weekend", False),
                        "time_of_day": entry.get("time_of_day", "afternoon"),
                        "emotions": entry.get("emotions", {}),
                        "topics": entry.get("topics", []),
                        "sentiment_score": entry.get("sentiment_score", 0.0),
                        "writing_quality": entry.get("writing_quality", {}),
                    }
                    journal_entries.append(entry_data)

                    # Build patterns for analysis
                    for emotion, score in entry_data["emotions"].items():
                        emotional_keywords[emotion] += score

                    for topic in entry_data["topics"]:
                        topic_clusters[topic].append(
                            {
                                "date": entry_data["date"],
                                "sentiment": entry_data["sentiment_score"],
                                "mood": entry_data["mood"],
                            }
                        )

                    writing_quality_metrics.append(entry_data["word_count"])
                    sentiment_evolution.append(
                        {
                            "date": entry_data["date"],
                            "sentiment": entry_data["sentiment_score"],
                        }
                    )

            # Use existing analysis methods for advanced metrics
            writing_consistency = (
                self._analyze_writing_consistency(journal_entries)
                if journal_entries
                else {}
            )
            emotional_progression = (
                self._track_emotional_progression(sentiment_evolution)
                if sentiment_evolution
                else {}
            )
            topic_focus_analysis = (
                self._analyze_topic_focus(topic_clusters) if topic_clusters else {}
            )
            therapeutic_indicators = (
                self._identify_therapeutic_progress(journal_entries)
                if journal_entries
                else {}
            )

            return {
                "journal_entries": journal_entries,
                "total_entries": len(journal_entries),
                "date_range": dataset.get("processing_metadata", {}).get(
                    "date_range", {}
                ),
                "emotional_keywords": dict(emotional_keywords),
                "topic_clusters": dict(topic_clusters),
                "writing_quality_metrics": {
                    "average_word_count": np.mean(writing_quality_metrics)
                    if writing_quality_metrics
                    else 0,
                    "consistency": writing_consistency,
                },
                "emotional_progression": emotional_progression,
                "topic_focus_analysis": topic_focus_analysis,
                "therapeutic_indicators": therapeutic_indicators,
                "sentiment_evolution": sentiment_evolution,
            }

        except Exception as e:
            logger.error(f"Error extracting journal data from dataset: {str(e)}")
            return {"journal_entries": [], "total_entries": 0, "date_range": {}}

    # Legacy data collection methods (now deprecated in favor of AI data interface)
    def _collect_mood_data(self, user, days: int) -> Dict[str, Any]:
        """Collect comprehensive mood tracking data for analysis"""
        try:
            from mood.models import MoodLog

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("-logged_at")

            # Enhanced data collection with more detailed analysis
            mood_entries = []
            daily_patterns = defaultdict(list)
            weekly_patterns = defaultdict(list)
            activity_patterns = defaultdict(list)
            note_keywords = defaultdict(int)

            for log in mood_logs:
                entry_data = {
                    "rating": log.mood_rating,
                    "activities": getattr(log, "activities", []),
                    "notes": getattr(log, "notes", ""),
                    "logged_at": log.logged_at.isoformat(),
                    "day_of_week": log.logged_at.weekday(),
                    "hour_of_day": log.logged_at.hour,
                    "date": log.logged_at.date().isoformat(),
                    "week_of_year": log.logged_at.isocalendar()[1],
                    "is_weekend": log.logged_at.weekday() >= 5,
                    "time_of_day": self._categorize_time_of_day(log.logged_at.hour),
                }
                mood_entries.append(entry_data)

                # Collect patterns for analysis
                daily_patterns[log.logged_at.date().isoformat()].append(log.mood_rating)
                weekly_patterns[log.logged_at.weekday()].append(log.mood_rating)

                # Activity correlation analysis
                for activity in getattr(log, "activities", []):
                    activity_patterns[activity].append(
                        {
                            "mood": log.mood_rating,
                            "time": log.logged_at.hour,
                            "day": log.logged_at.weekday(),
                        }
                    )

                # Extract keywords from notes for sentiment analysis
                if hasattr(log, "notes") and log.notes:
                    keywords = self._extract_mood_keywords(log.notes.lower())
                    for keyword in keywords:
                        note_keywords[keyword] += 1

            # Calculate advanced metrics
            mood_volatility = self._calculate_detailed_volatility(mood_entries)
            activity_effectiveness = self._analyze_activity_effectiveness(
                activity_patterns
            )
            temporal_insights = self._analyze_detailed_temporal_patterns(mood_entries)
            stress_indicators = self._identify_stress_patterns(
                mood_entries, note_keywords
            )

            return {
                "mood_logs": mood_entries,
                "total_logs": mood_logs.count(),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days,
                },
                "daily_patterns": dict(daily_patterns),
                "weekly_patterns": dict(weekly_patterns),
                "activity_patterns": dict(activity_patterns),
                "note_keywords": dict(note_keywords),
                "mood_volatility": mood_volatility,
                "activity_effectiveness": activity_effectiveness,
                "temporal_insights": temporal_insights,
                "stress_indicators": stress_indicators,
            }

        except Exception as e:
            logger.error(f"Error collecting mood data: {str(e)}")
            return {"mood_logs": [], "total_logs": 0, "date_range": {}}

    def _collect_journal_data(self, user, days: int) -> Dict[str, Any]:
        """Collect comprehensive journal data for analysis"""
        try:
            from journal.models import JournalEntry

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            journal_entries = JournalEntry.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).order_by("-created_at")

            # Enhanced journal analysis
            entries_data = []
            emotional_keywords = defaultdict(int)
            topic_clusters = defaultdict(list)
            writing_quality_metrics = []
            sentiment_evolution = []

            for entry in journal_entries:
                # Detailed content analysis
                content = entry.content
                word_count = len(content.split())
                sentence_count = len([s for s in content.split(".") if s.strip()])

                # Extract emotional indicators
                emotions = self._analyze_entry_emotions(content)
                topics = self._categorize_entry_topics(content)
                sentiment = self._calculate_entry_sentiment(content)

                entry_data = {
                    "content": content[:500],  # Limit for analysis
                    "full_content_length": len(content),
                    "word_count": word_count,
                    "sentence_count": sentence_count,
                    "mood": getattr(entry, "mood", "neutral"),
                    "activities": getattr(entry, "activities", []),
                    "created_at": entry.created_at.isoformat(),
                    "day_of_week": entry.created_at.weekday(),
                    "hour_of_day": entry.created_at.hour,
                    "date": entry.created_at.date().isoformat(),
                    "is_weekend": entry.created_at.weekday() >= 5,
                    "time_of_day": self._categorize_time_of_day(entry.created_at.hour),
                    "emotions": emotions,
                    "topics": topics,
                    "sentiment_score": sentiment,
                    "writing_quality": self._assess_writing_quality(
                        content, word_count, sentence_count
                    ),
                }
                entries_data.append(entry_data)

                # Collect patterns
                for emotion, score in emotions.items():
                    emotional_keywords[emotion] += score

                for topic in topics:
                    topic_clusters[topic].append(
                        {
                            "date": entry.created_at.date().isoformat(),
                            "sentiment": sentiment,
                            "mood": getattr(entry, "mood", "neutral"),
                        }
                    )

                writing_quality_metrics.append(word_count)
                sentiment_evolution.append(
                    {
                        "date": entry.created_at.date().isoformat(),
                        "sentiment": sentiment,
                    }
                )

            # Advanced analysis
            writing_consistency = self._analyze_writing_consistency(entries_data)
            emotional_progression = self._track_emotional_progression(
                sentiment_evolution
            )
            topic_focus_analysis = self._analyze_topic_focus(topic_clusters)
            therapeutic_indicators = self._identify_therapeutic_progress(entries_data)

            return {
                "journal_entries": entries_data,
                "total_entries": journal_entries.count(),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days,
                },
                "emotional_keywords": dict(emotional_keywords),
                "topic_clusters": dict(topic_clusters),
                "writing_quality_metrics": {
                    "average_word_count": np.mean(writing_quality_metrics)
                    if writing_quality_metrics
                    else 0,
                    "consistency": writing_consistency,
                },
                "emotional_progression": emotional_progression,
                "topic_focus_analysis": topic_focus_analysis,
                "therapeutic_indicators": therapeutic_indicators,
                "sentiment_evolution": sentiment_evolution,
            }

        except Exception as e:
            logger.error(f"Error collecting journal data: {str(e)}")
            return {"journal_entries": [], "total_entries": 0, "date_range": {}}

    def _categorize_time_of_day(self, hour: int) -> str:
        """Categorize hour into time periods"""
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    def _extract_mood_keywords(self, text: str) -> List[str]:
        """Extract mood-related keywords from text"""
        mood_keywords = {
            "positive": [
                "happy",
                "good",
                "great",
                "amazing",
                "wonderful",
                "excited",
                "content",
                "peaceful",
            ],
            "negative": [
                "sad",
                "bad",
                "awful",
                "terrible",
                "depressed",
                "down",
                "upset",
                "frustrated",
            ],
            "anxious": [
                "anxious",
                "worried",
                "stressed",
                "nervous",
                "panic",
                "overwhelmed",
                "tense",
            ],
            "tired": ["tired", "exhausted", "drained", "sleepy", "fatigue", "worn out"],
            "energetic": [
                "energetic",
                "active",
                "motivated",
                "pumped",
                "vibrant",
                "alert",
            ],
            "calm": ["calm", "relaxed", "serene", "tranquil", "peaceful", "centered"],
        }

        found_keywords = []
        for category, keywords in mood_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(f"{category}_{keyword}")

        return found_keywords

    def _calculate_detailed_volatility(self, mood_entries: List[Dict]) -> Dict:
        """Calculate detailed mood volatility metrics"""
        if len(mood_entries) < 2:
            return {"overall": 0, "daily": 0, "weekly": 0}

        ratings = [entry["rating"] for entry in mood_entries]

        # Overall volatility
        overall_volatility = np.std(ratings)

        # Daily volatility (mood changes within same day)
        daily_groups = defaultdict(list)
        for entry in mood_entries:
            daily_groups[entry["date"]].append(entry["rating"])

        daily_volatilities = []
        for day_ratings in daily_groups.values():
            if len(day_ratings) > 1:
                daily_volatilities.append(np.std(day_ratings))

        daily_volatility = np.mean(daily_volatilities) if daily_volatilities else 0

        # Weekly pattern volatility
        weekly_ratings = defaultdict(list)
        for entry in mood_entries:
            weekly_ratings[entry["day_of_week"]].append(entry["rating"])

        weekly_averages = [
            np.mean(ratings) for ratings in weekly_ratings.values() if ratings
        ]
        weekly_volatility = np.std(weekly_averages) if len(weekly_averages) > 1 else 0

        return {
            "overall": float(overall_volatility),
            "daily": float(daily_volatility),
            "weekly": float(weekly_volatility),
            "stability_rating": self._rate_mood_stability(overall_volatility),
        }

    def _analyze_activity_effectiveness(self, activity_patterns: Dict) -> Dict:
        """Analyze which activities are most effective for mood improvement"""
        effectiveness = {}

        for activity, mood_data in activity_patterns.items():
            if len(mood_data) < 2:
                continue

            moods = [data["mood"] for data in mood_data]
            times = [data["time"] for data in mood_data]
            days = [data["day"] for data in mood_data]

            effectiveness[activity] = {
                "average_mood": float(np.mean(moods)),
                "mood_consistency": 1.0
                / (1.0 + np.std(moods)),  # Higher is more consistent
                "frequency": len(mood_data),
                "best_times": self._find_optimal_times(times, moods),
                "best_days": self._find_optimal_days(days, moods),
                "effectiveness_score": self._calculate_activity_effectiveness_score(
                    moods
                ),
            }

        return effectiveness

    def _analyze_detailed_temporal_patterns(self, mood_entries: List[Dict]) -> Dict:
        """Analyze detailed temporal patterns in mood data"""
        patterns = {
            "hourly_trends": defaultdict(list),
            "daily_trends": defaultdict(list),
            "weekend_vs_weekday": {"weekend": [], "weekday": []},
            "time_of_day_patterns": defaultdict(list),
        }

        for entry in mood_entries:
            patterns["hourly_trends"][entry["hour_of_day"]].append(entry["rating"])
            patterns["daily_trends"][entry["day_of_week"]].append(entry["rating"])

            if entry["is_weekend"]:
                patterns["weekend_vs_weekday"]["weekend"].append(entry["rating"])
            else:
                patterns["weekend_vs_weekday"]["weekday"].append(entry["rating"])

            patterns["time_of_day_patterns"][entry["time_of_day"]].append(
                entry["rating"]
            )

        # Calculate averages and insights
        insights = {
            "best_hours": self._find_best_time_periods(patterns["hourly_trends"]),
            "best_days": self._find_best_time_periods(patterns["daily_trends"]),
            "weekend_preference": self._compare_weekend_weekday(
                patterns["weekend_vs_weekday"]
            ),
            "optimal_time_of_day": self._find_best_time_periods(
                patterns["time_of_day_patterns"]
            ),
        }

        return insights

    def _identify_stress_patterns(
        self, mood_entries: List[Dict], note_keywords: Dict
    ) -> Dict:
        """Identify stress patterns from mood and notes"""
        stress_indicators = {
            "stress_keywords": 0,
            "low_mood_frequency": 0,
            "mood_drops": 0,
            "stress_times": defaultdict(int),
            "stress_days": defaultdict(int),
        }

        # Count stress-related keywords
        stress_words = [
            "stress",
            "anxious",
            "worried",
            "overwhelmed",
            "pressure",
            "tense",
        ]
        for keyword, count in note_keywords.items():
            if any(stress_word in keyword for stress_word in stress_words):
                stress_indicators["stress_keywords"] += count

        # Analyze mood patterns for stress indicators
        for i, entry in enumerate(mood_entries):
            if entry["rating"] <= 3:  # Low mood threshold
                stress_indicators["low_mood_frequency"] += 1
                stress_indicators["stress_times"][entry["time_of_day"]] += 1
                stress_indicators["stress_days"][entry["day_of_week"]] += 1

            # Detect mood drops
            if i > 0 and entry["rating"] < mood_entries[i - 1]["rating"] - 2:
                stress_indicators["mood_drops"] += 1

        return stress_indicators

    def _analyze_entry_emotions(self, content: str) -> Dict[str, int]:
        """Analyze emotions in journal entry content"""
        emotion_patterns = {
            "joy": ["happy", "joyful", "excited", "elated", "cheerful", "delighted"],
            "sadness": ["sad", "depressed", "down", "melancholy", "grief", "sorrow"],
            "anger": ["angry", "furious", "mad", "irritated", "frustrated", "annoyed"],
            "fear": ["afraid", "scared", "fearful", "terrified", "anxious", "worried"],
            "surprise": ["surprised", "amazed", "astonished", "shocked", "stunned"],
            "disgust": ["disgusted", "revolted", "appalled", "repulsed"],
            "love": ["love", "adore", "cherish", "treasure", "devoted"],
            "hope": ["hopeful", "optimistic", "confident", "positive", "encouraged"],
            "guilt": ["guilty", "ashamed", "regret", "remorse", "sorry"],
            "pride": ["proud", "accomplished", "successful", "achieved", "satisfied"],
        }

        content_lower = content.lower()
        emotions = {}

        for emotion, keywords in emotion_patterns.items():
            count = sum(1 for keyword in keywords if keyword in content_lower)
            if count > 0:
                emotions[emotion] = count

        return emotions

    def _categorize_entry_topics(self, content: str) -> List[str]:
        """Categorize journal entry topics"""
        topic_keywords = {
            "work": ["work", "job", "career", "boss", "colleague", "office", "project"],
            "relationships": [
                "friend",
                "family",
                "partner",
                "spouse",
                "parent",
                "child",
                "relationship",
            ],
            "health": [
                "health",
                "doctor",
                "medication",
                "exercise",
                "sleep",
                "diet",
                "medical",
            ],
            "personal_growth": [
                "goal",
                "growth",
                "learn",
                "improve",
                "development",
                "progress",
            ],
            "finances": ["money", "financial", "budget", "expenses", "income", "debt"],
            "hobbies": [
                "hobby",
                "interest",
                "passion",
                "creative",
                "art",
                "music",
                "sport",
            ],
            "travel": ["travel", "trip", "vacation", "journey", "adventure", "explore"],
            "education": [
                "school",
                "study",
                "learn",
                "education",
                "course",
                "university",
            ],
            "spirituality": [
                "spiritual",
                "faith",
                "prayer",
                "meditation",
                "belief",
                "religion",
            ],
            "daily_life": ["daily", "routine", "chores", "errands", "household"],
        }

        content_lower = content.lower()
        detected_topics = []

        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                detected_topics.append(topic)

        return detected_topics

    def _calculate_entry_sentiment(self, content: str) -> float:
        """Calculate sentiment score for journal entry"""
        positive_words = [
            "good",
            "great",
            "excellent",
            "wonderful",
            "amazing",
            "happy",
            "love",
            "perfect",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "horrible",
            "sad",
            "angry",
            "frustrated",
        ]

        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        total_words = len(content.split())
        if total_words == 0:
            return 0.0

        sentiment_score = (positive_count - negative_count) / total_words
        return max(-1.0, min(1.0, sentiment_score))  # Normalize to -1 to 1

    def _build_mood_tips_prompt(self, mood_analysis: Dict, tip_count: int) -> str:
        """Build enhanced prompt for mood-based tips"""
        return f"""As a mental health professional, analyze this comprehensive mood data and provide {tip_count} highly personalized tips:

DETAILED MOOD ANALYSIS:
- Average mood: {mood_analysis.get('average_mood', 5)}/10
- Mood trend: {mood_analysis.get('mood_trend', 'stable')}
- Mood stability: {mood_analysis.get('mood_stability', 'unknown')}
- Volatility metrics: {mood_analysis.get('mood_volatility', {})}
- Activity effectiveness: {mood_analysis.get('activity_effectiveness', {})}
- Temporal insights: {mood_analysis.get('temporal_insights', {})}
- Stress indicators: {mood_analysis.get('stress_indicators', {})}
- Best performing activities: {list(mood_analysis.get('activity_analysis', {}).keys())[:5]}
- Optimal timing patterns: {mood_analysis.get('temporal_patterns', {})}

PERSONALIZATION FACTORS:
- Most effective activities: {self._get_top_activities(mood_analysis)}
- Stress patterns: {mood_analysis.get('stress_indicators', {})}
- Best times for interventions: {self._get_optimal_intervention_times(mood_analysis)}
- Mood volatility level: {mood_analysis.get('mood_volatility', {}).get('stability_rating', 'unknown')}

Provide {tip_count} highly specific, actionable tips in JSON format that address the user's unique patterns:
{{
    "tips": [
        {{
            "title": "<specific tip title>",
            "description": "<detailed, personalized description based on user's patterns>",
            "category": "<mood|activity|routine|mindfulness|stress_management>",
            "difficulty": "<easy|medium|hard>",
            "estimated_time": "<time needed>",
            "expected_benefit": "<specific benefit based on user's data>",
            "personalization_reason": "<why this tip is specifically for this user>",
            "optimal_timing": "<when to implement based on user's patterns>",
            "success_indicators": "<how to measure if it's working>"
        }}
    ]
}}

Focus on tips that directly address the user's specific patterns, stress indicators, and optimal timing preferences."""

    def _build_journal_tips_prompt(self, journal_analysis: Dict, tip_count: int) -> str:
        """Build enhanced prompt for journal-based tips"""
        return f"""As a mental health professional, analyze this comprehensive journaling data and provide {tip_count} highly personalized tips:

DETAILED JOURNAL ANALYSIS:
- Writing frequency: {journal_analysis.get('writing_frequency', 0):.2f} entries per day
- Average entry length: {journal_analysis.get('average_entry_length', 0):.0f} words
- Writing quality metrics: {journal_analysis.get('writing_quality_metrics', {})}
- Emotional progression: {journal_analysis.get('emotional_progression', {})}
- Topic focus analysis: {journal_analysis.get('topic_focus_analysis', {})}
- Therapeutic indicators: {journal_analysis.get('therapeutic_indicators', {})}
- Dominant emotions: {journal_analysis.get('emotional_keywords', {})}
- Main topics: {journal_analysis.get('topic_clusters', {})}
- Sentiment evolution: {journal_analysis.get('sentiment_evolution', [])}

PERSONALIZATION FACTORS:
- Writing consistency: {journal_analysis.get('writing_quality_metrics', {}).get('consistency', 'unknown')}
- Emotional patterns: {self._summarize_emotional_patterns(journal_analysis)}
- Topic focus areas: {self._get_main_topic_focuses(journal_analysis)}
- Therapeutic progress indicators: {journal_analysis.get('therapeutic_indicators', {})}

Provide {tip_count} highly specific, actionable journaling tips in JSON format:
{{
    "tips": [
        {{
            "title": "<specific tip title>",
            "description": "<detailed, personalized description based on user's patterns>",
            "category": "<writing|reflection|structure|habit|emotional_processing>",
            "difficulty": "<easy|medium|hard>",
            "estimated_time": "<time needed>",
            "expected_benefit": "<specific benefit based on user's data>",
            "personalization_reason": "<why this tip is specifically for this user>",
            "implementation_guide": "<step-by-step how to implement>",
            "success_indicators": "<how to measure improvement>"
        }}
    ]
}}

Focus on tips that address the user's specific writing patterns, emotional themes, and areas for therapeutic growth."""

    def _get_top_activities(self, mood_analysis: Dict) -> List[str]:
        """Get top performing activities from mood analysis"""
        activity_effectiveness = mood_analysis.get("activity_effectiveness", {})
        if not activity_effectiveness:
            return []

        sorted_activities = sorted(
            activity_effectiveness.items(),
            key=lambda x: x[1].get("effectiveness_score", 0),
            reverse=True,
        )

        return [activity for activity, _ in sorted_activities[:3]]

    def _get_optimal_intervention_times(self, mood_analysis: Dict) -> Dict:
        """Get optimal times for interventions based on mood patterns"""
        temporal_insights = mood_analysis.get("temporal_insights", {})
        return {
            "best_times": temporal_insights.get("best_hours", []),
            "best_days": temporal_insights.get("best_days", []),
            "avoid_times": temporal_insights.get("worst_hours", []),
        }

    def _summarize_emotional_patterns(self, journal_analysis: Dict) -> Dict:
        """Summarize key emotional patterns from journal analysis"""
        emotional_keywords = journal_analysis.get("emotional_keywords", {})
        if not emotional_keywords:
            return {}

        # Find dominant emotions
        sorted_emotions = sorted(
            emotional_keywords.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "dominant_emotions": [emotion for emotion, _ in sorted_emotions[:3]],
            "emotional_diversity": len(emotional_keywords),
            "primary_emotional_theme": sorted_emotions[0][0]
            if sorted_emotions
            else "neutral",
        }

    def _get_main_topic_focuses(self, journal_analysis: Dict) -> List[str]:
        """Get main topic focuses from journal analysis"""
        topic_clusters = journal_analysis.get("topic_clusters", {})
        if not topic_clusters:
            return []

        # Sort topics by frequency and engagement
        sorted_topics = sorted(
            topic_clusters.items(), key=lambda x: len(x[1]), reverse=True
        )

        return [topic for topic, _ in sorted_topics[:3]]


# Create singleton instance
tips_service = TipsService()

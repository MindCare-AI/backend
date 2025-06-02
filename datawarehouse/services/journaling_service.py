# datawarehouse/services/journaling_service.py
"""
Dedicated service for collecting and processing journaling data
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
import re
from collections import Counter

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class JournalingDataSnapshot:
    """Structured representation of journaling data"""
    user_id: int
    collection_date: datetime
    period_days: int
    writing_statistics: Dict[str, Any]
    sentiment_analysis: Dict[str, Any]
    topic_analysis: Dict[str, Any]
    mood_correlation: Dict[str, Any]
    writing_patterns: Dict[str, Any]
    emotional_insights: Dict[str, Any]
    raw_entries: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class JournalingCollectionService:
    """Dedicated service for journaling data collection and analysis"""
    
    def __init__(self):
        self.cache_timeout = 900  # 15 minutes
        self.collection_stats = {
            'total_collections': 0,
            'avg_collection_time': 0.0,
            'cache_hit_rate': 0.0,
            'error_rate': 0.0
        }
        
        # Sentiment analysis keywords
        self.positive_words = [
            'happy', 'joy', 'excited', 'grateful', 'peaceful', 'content', 'satisfied',
            'proud', 'accomplished', 'optimistic', 'hopeful', 'blessed', 'lucky',
            'wonderful', 'amazing', 'great', 'good', 'excellent', 'fantastic',
            'love', 'beautiful', 'success', 'achievement', 'progress', 'improvement'
        ]
        
        self.negative_words = [
            'sad', 'depressed', 'anxious', 'worried', 'stressed', 'angry', 'frustrated',
            'upset', 'disappointed', 'lonely', 'scared', 'afraid', 'nervous',
            'terrible', 'awful', 'bad', 'horrible', 'miserable', 'pain', 'hurt',
            'struggle', 'difficult', 'hard', 'overwhelming', 'exhausted', 'tired'
        ]
        
        # Topic keywords for categorization
        self.topic_keywords = {
            'work': ['work', 'job', 'career', 'office', 'boss', 'colleague', 'meeting', 'project'],
            'relationships': ['family', 'friend', 'partner', 'spouse', 'relationship', 'love', 'social'],
            'health': ['health', 'exercise', 'diet', 'fitness', 'medical', 'doctor', 'medication'],
            'therapy': ['therapy', 'therapist', 'counseling', 'session', 'treatment', 'mental health'],
            'personal_growth': ['growth', 'learning', 'goal', 'achievement', 'progress', 'development'],
            'daily_life': ['daily', 'routine', 'home', 'chores', 'cooking', 'cleaning'],
            'hobbies': ['hobby', 'reading', 'music', 'art', 'sports', 'game', 'movie'],
            'financial': ['money', 'financial', 'budget', 'expense', 'income', 'debt']
        }
    
    def collect_journaling_data(self, user_id: int, days: int = 30) -> JournalingDataSnapshot:
        """
        Collect comprehensive journaling data for a user
        
        Args:
            user_id: User identifier
            days: Number of days to collect data for
            
        Returns:
            JournalingDataSnapshot with all journaling-related data
        """
        import time
        start_time = time.time()
        logger.info(f"Starting journaling data collection for user {user_id}, {days} days")
        
        try:
            # Check cache first
            cache_key = f"journaling_data:{user_id}:{days}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached journaling data for user {user_id}")
                self.collection_stats['cache_hit_rate'] += 1
                return JournalingDataSnapshot(**cached_data)
            
            # Get user object
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError(f"User {user_id} not found")
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Collect journaling data
            journal_data = self._collect_raw_journal_data(user, start_date, end_date)
            
            # Analyze journaling patterns
            writing_statistics = self._calculate_writing_statistics(journal_data)
            sentiment_analysis = self._analyze_sentiment(journal_data)
            topic_analysis = self._analyze_topics(journal_data)
            mood_correlation = self._analyze_mood_correlation(journal_data)
            writing_patterns = self._analyze_writing_patterns(journal_data)
            emotional_insights = self._extract_emotional_insights(journal_data)
            
            # Create snapshot
            snapshot = JournalingDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                writing_statistics=writing_statistics,
                sentiment_analysis=sentiment_analysis,
                topic_analysis=topic_analysis,
                mood_correlation=mood_correlation,
                writing_patterns=writing_patterns,
                emotional_insights=emotional_insights,
                raw_entries=journal_data.to_dict('records') if not journal_data.empty else [],
                metadata={
                    'collection_time': time.time() - start_time,
                    'total_entries': len(journal_data),
                    'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                    'version': '1.0'
                }
            )
            
            # Cache the results
            from dataclasses import asdict
            cache.set(cache_key, asdict(snapshot), self.cache_timeout)
            
            # Update performance metrics
            self._update_performance_metrics(start_time, len(journal_data))
            
            logger.info(f"Journaling data collection completed for user {user_id}")
            return snapshot
            
        except Exception as exc:
            logger.error(f"Journaling data collection failed for user {user_id}: {str(exc)}")
            self.collection_stats['error_rate'] += 1
            raise
    
    def _collect_raw_journal_data(self, user, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Collect raw journal data from database"""
        try:
            from journal.models import JournalEntry
            
            entries = JournalEntry.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values(
                'id', 'title', 'content', 'mood_before', 'mood_after',
                'created_at', 'category_id', 'tags'
            )
            
            if not entries:
                return pd.DataFrame()
            
            # Convert to pandas DataFrame
            df = pd.DataFrame(list(entries))
            df['created_at'] = pd.to_datetime(df['created_at'])
            df = df.sort_values('created_at')
            
            return df
            
        except Exception as exc:
            logger.error(f"Error collecting raw journal data: {str(exc)}")
            return pd.DataFrame()
    
    def _calculate_writing_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive writing statistics"""
        try:
            if df.empty:
                return self._get_empty_writing_statistics()
            
            # Basic counts
            total_entries = len(df)
            
            # Content analysis
            content_lengths = []
            title_lengths = []
            word_counts = []
            
            for _, row in df.iterrows():
                content = str(row.get('content', ''))
                title = str(row.get('title', ''))
                
                content_lengths.append(len(content))
                title_lengths.append(len(title))
                word_counts.append(len(content.split()) if content else 0)
            
            statistics = {
                'total_entries': total_entries,
                'avg_content_length': np.mean(content_lengths) if content_lengths else 0,
                'avg_word_count': np.mean(word_counts) if word_counts else 0,
                'avg_title_length': np.mean(title_lengths) if title_lengths else 0,
                'min_content_length': min(content_lengths) if content_lengths else 0,
                'max_content_length': max(content_lengths) if content_lengths else 0,
                'total_words_written': sum(word_counts),
                'content_length_std': np.std(content_lengths) if len(content_lengths) > 1 else 0,
                'writing_consistency': {
                    'entries_per_week': total_entries / max(1, len(df) / 7) if len(df) > 0 else 0,
                    'avg_days_between_entries': self._calculate_avg_days_between_entries(df)
                }
            }
            
            # Writing quality indicators
            if content_lengths:
                statistics['writing_depth_category'] = self._categorize_writing_depth(np.mean(content_lengths))
            
            return statistics
            
        except Exception as exc:
            logger.error(f"Error calculating writing statistics: {str(exc)}")
            return self._get_empty_writing_statistics()
    
    def _analyze_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sentiment in journal entries"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            sentiment_scores = []
            emotional_intensity = []
            
            for _, row in df.iterrows():
                content = str(row.get('content', '')).lower()
                
                # Count positive and negative words
                positive_count = sum(1 for word in self.positive_words if word in content)
                negative_count = sum(1 for word in self.negative_words if word in content)
                
                # Calculate sentiment score (-1 to 1)
                total_sentiment_words = positive_count + negative_count
                if total_sentiment_words > 0:
                    sentiment = (positive_count - negative_count) / total_sentiment_words
                    intensity = total_sentiment_words / len(content.split()) if content.split() else 0
                else:
                    sentiment = 0
                    intensity = 0
                
                sentiment_scores.append(sentiment)
                emotional_intensity.append(intensity)
            
            if not sentiment_scores:
                return {}
            
            avg_sentiment = np.mean(sentiment_scores)
            avg_intensity = np.mean(emotional_intensity)
            
            # Determine overall sentiment trend
            if avg_sentiment > 0.2:
                trend = 'positive'
            elif avg_sentiment < -0.2:
                trend = 'negative'
            else:
                trend = 'neutral'
            
            # Sentiment progression over time
            sentiment_progression = self._analyze_sentiment_progression(df, sentiment_scores)
            
            return {
                'average_sentiment': float(avg_sentiment),
                'sentiment_trend': trend,
                'emotional_intensity': float(avg_intensity),
                'sentiment_distribution': {
                    'positive_entries': len([s for s in sentiment_scores if s > 0.1]),
                    'negative_entries': len([s for s in sentiment_scores if s < -0.1]),
                    'neutral_entries': len([s for s in sentiment_scores if -0.1 <= s <= 0.1])
                },
                'sentiment_volatility': float(np.std(sentiment_scores)) if len(sentiment_scores) > 1 else 0,
                'sentiment_progression': sentiment_progression,
                'most_positive_entry_index': int(np.argmax(sentiment_scores)) if sentiment_scores else None,
                'most_negative_entry_index': int(np.argmin(sentiment_scores)) if sentiment_scores else None
            }
            
        except Exception as exc:
            logger.error(f"Error analyzing sentiment: {str(exc)}")
            return {}
    
    def _analyze_topics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze topics and themes in journal entries"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            topic_occurrences = {topic: 0 for topic in self.topic_keywords.keys()}
            entry_topics = []
            all_words = []
            
            for _, row in df.iterrows():
                content = str(row.get('content', '')).lower()
                title = str(row.get('title', '')).lower()
                combined_text = f"{content} {title}"
                
                # Extract words for frequency analysis
                words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_text)
                all_words.extend(words)
                
                # Identify topics for this entry
                entry_topic_list = []
                for topic, keywords in self.topic_keywords.items():
                    if any(keyword in combined_text for keyword in keywords):
                        topic_occurrences[topic] += 1
                        entry_topic_list.append(topic)
                
                entry_topics.append(entry_topic_list)
            
            # Calculate topic statistics
            total_entries = len(df)
            topic_percentages = {
                topic: (count / total_entries) * 100 if total_entries > 0 else 0
                for topic, count in topic_occurrences.items()
            }
            
            # Most common words (excluding common stop words)
            stop_words = {'the', 'and', 'but', 'for', 'are', 'with', 'was', 'were', 'been', 'have', 'has', 'had', 'this', 'that', 'they', 'them', 'their', 'what', 'when', 'where', 'who', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now'}
            filtered_words = [word for word in all_words if word not in stop_words and len(word) > 3]
            word_frequency = Counter(filtered_words).most_common(20)
            
            return {
                'topic_occurrences': topic_occurrences,
                'topic_percentages': topic_percentages,
                'most_common_topics': sorted(topic_percentages.items(), key=lambda x: x[1], reverse=True)[:5],
                'entries_per_topic': {topic: count for topic, count in topic_occurrences.items() if count > 0},
                'word_frequency': dict(word_frequency),
                'topic_diversity': len([topic for topic, count in topic_occurrences.items() if count > 0]),
                'avg_topics_per_entry': np.mean([len(topics) for topics in entry_topics]) if entry_topics else 0
            }
            
        except Exception as exc:
            logger.error(f"Error analyzing topics: {str(exc)}")
            return {}
    
    def _analyze_mood_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze correlation between journaling and mood changes"""
        try:
            if df.empty or 'mood_before' not in df or 'mood_after' not in df:
                return {}
            
            # Filter entries with valid mood data
            mood_data = df.dropna(subset=['mood_before', 'mood_after'])
            
            if mood_data.empty:
                return {}
            
            mood_before = mood_data['mood_before'].values
            mood_after = mood_data['mood_after'].values
            mood_changes = mood_after - mood_before
            
            analysis = {
                'entries_with_mood_data': len(mood_data),
                'avg_mood_before': float(np.mean(mood_before)),
                'avg_mood_after': float(np.mean(mood_after)),
                'avg_mood_change': float(np.mean(mood_changes)),
                'mood_improvement_rate': len(mood_changes[mood_changes > 0]) / len(mood_changes) * 100 if len(mood_changes) > 0 else 0,
                'significant_improvements': len(mood_changes[mood_changes >= 2]) / len(mood_changes) * 100 if len(mood_changes) > 0 else 0,
                'mood_decline_rate': len(mood_changes[mood_changes < 0]) / len(mood_changes) * 100 if len(mood_changes) > 0 else 0
            }
            
            # Categorize the impact of journaling
            avg_change = analysis['avg_mood_change']
            if avg_change > 1:
                analysis['journaling_impact'] = 'highly_beneficial'
            elif avg_change > 0.5:
                analysis['journaling_impact'] = 'moderately_beneficial'
            elif avg_change > 0:
                analysis['journaling_impact'] = 'slightly_beneficial'
            elif avg_change > -0.5:
                analysis['journaling_impact'] = 'minimal_impact'
            else:
                analysis['journaling_impact'] = 'concerning_pattern'
            
            return analysis
            
        except Exception as exc:
            logger.error(f"Error analyzing mood correlation: {str(exc)}")
            return {}
    
    def _analyze_writing_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze writing patterns and habits"""
        try:
            if df.empty or 'created_at' not in df:
                return {}
            
            # Time-based analysis
            df['hour'] = df['created_at'].dt.hour
            df['day_of_week'] = df['created_at'].dt.day_name()
            df['date'] = df['created_at'].dt.date
            
            # Daily patterns
            daily_counts = df.groupby('date').size()
            hourly_pattern = df['hour'].value_counts().sort_index().to_dict()
            weekly_pattern = df['day_of_week'].value_counts().to_dict()
            
            # Writing frequency analysis
            writing_frequency = self._analyze_writing_frequency(df)
            
            # Streak analysis
            streak_analysis = self._analyze_writing_streaks(df)
            
            return {
                'hourly_pattern': hourly_pattern,
                'weekly_pattern': weekly_pattern,
                'preferred_writing_times': {
                    'most_active_hour': int(df['hour'].mode().iloc[0]) if not df['hour'].mode().empty else None,
                    'most_active_day': df['day_of_week'].mode().iloc[0] if not df['day_of_week'].mode().empty else None
                },
                'writing_frequency': writing_frequency,
                'streak_analysis': streak_analysis,
                'consistency_score': self._calculate_consistency_score(daily_counts)
            }
            
        except Exception as exc:
            logger.error(f"Error analyzing writing patterns: {str(exc)}")
            return {}
    
    def _extract_emotional_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract emotional insights from journal content"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            # Emotional themes extraction
            emotional_themes = {
                'anxiety': ['anxious', 'worried', 'nervous', 'panic', 'fear', 'stress'],
                'depression': ['sad', 'depressed', 'hopeless', 'empty', 'numb', 'worthless'],
                'happiness': ['happy', 'joy', 'excited', 'cheerful', 'delighted', 'elated'],
                'anger': ['angry', 'frustrated', 'irritated', 'mad', 'furious', 'annoyed'],
                'gratitude': ['grateful', 'thankful', 'blessed', 'appreciative', 'lucky'],
                'hope': ['hopeful', 'optimistic', 'positive', 'confident', 'determined']
            }
            
            theme_counts = {theme: 0 for theme in emotional_themes.keys()}
            emotional_progression = []
            
            for _, row in df.iterrows():
                content = str(row.get('content', '')).lower()
                entry_emotions = []
                
                for theme, keywords in emotional_themes.items():
                    if any(keyword in content for keyword in keywords):
                        theme_counts[theme] += 1
                        entry_emotions.append(theme)
                
                emotional_progression.append(entry_emotions)
            
            # Calculate emotional diversity
            total_emotional_mentions = sum(theme_counts.values())
            emotional_distribution = {
                theme: (count / total_emotional_mentions) * 100 if total_emotional_mentions > 0 else 0
                for theme, count in theme_counts.items()
            }
            
            return {
                'emotional_themes': theme_counts,
                'emotional_distribution': emotional_distribution,
                'dominant_emotions': sorted(emotional_distribution.items(), key=lambda x: x[1], reverse=True)[:3],
                'emotional_diversity': len([theme for theme, count in theme_counts.items() if count > 0]),
                'emotional_progression': emotional_progression,
                'emotional_balance_score': self._calculate_emotional_balance(theme_counts)
            }
            
        except Exception as exc:
            logger.error(f"Error extracting emotional insights: {str(exc)}")
            return {}
    
    def _analyze_sentiment_progression(self, df: pd.DataFrame, sentiment_scores: List[float]) -> Dict[str, Any]:
        """Analyze how sentiment changes over time"""
        try:
            if len(sentiment_scores) < 2:
                return {}
            
            # Calculate trend
            x = np.arange(len(sentiment_scores))
            slope, _ = np.polyfit(x, sentiment_scores, 1)
            
            # Determine progression
            if slope > 0.1:
                progression = 'improving'
            elif slope < -0.1:
                progression = 'declining'
            else:
                progression = 'stable'
            
            # Weekly averages if enough data
            weekly_sentiment = {}
            if len(df) > 7:
                df_copy = df.copy()
                df_copy['sentiment'] = sentiment_scores
                df_copy['week'] = df_copy['created_at'].dt.isocalendar().week
                weekly_sentiment = df_copy.groupby('week')['sentiment'].mean().to_dict()
            
            return {
                'progression_direction': progression,
                'progression_strength': abs(float(slope)),
                'weekly_averages': weekly_sentiment,
                'recent_trend': np.mean(sentiment_scores[-5:]) if len(sentiment_scores) >= 5 else np.mean(sentiment_scores)
            }
            
        except Exception as exc:
            logger.error(f"Error analyzing sentiment progression: {str(exc)}")
            return {}
    
    def _calculate_avg_days_between_entries(self, df: pd.DataFrame) -> float:
        """Calculate average days between journal entries"""
        try:
            if len(df) < 2:
                return 0.0
            
            dates = sorted(df['created_at'].dt.date.unique())
            intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            
            return float(np.mean(intervals)) if intervals else 0.0
            
        except Exception:
            return 0.0
    
    def _categorize_writing_depth(self, avg_content_length: float) -> str:
        """Categorize writing depth based on average content length"""
        if avg_content_length > 1000:
            return 'very_detailed'
        elif avg_content_length > 500:
            return 'detailed'
        elif avg_content_length > 200:
            return 'moderate'
        elif avg_content_length > 50:
            return 'brief'
        else:
            return 'minimal'
    
    def _analyze_writing_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze writing frequency patterns"""
        try:
            if df.empty:
                return {}
            
            daily_counts = df.groupby('date').size()
            
            return {
                'avg_entries_per_day': float(daily_counts.mean()),
                'max_entries_per_day': int(daily_counts.max()),
                'total_writing_days': len(daily_counts),
                'writing_consistency': float(daily_counts.std()) if len(daily_counts) > 1 else 0.0,
                'days_with_multiple_entries': len(daily_counts[daily_counts > 1])
            }
            
        except Exception:
            return {}
    
    def _analyze_writing_streaks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze writing streaks and gaps"""
        try:
            if df.empty:
                return {}
            
            dates = sorted(df['created_at'].dt.date.unique())
            
            # Calculate streaks
            current_streak = 1
            max_streak = 1
            streaks = []
            
            for i in range(1, len(dates)):
                if (dates[i] - dates[i-1]).days == 1:
                    current_streak += 1
                else:
                    streaks.append(current_streak)
                    max_streak = max(max_streak, current_streak)
                    current_streak = 1
            
            streaks.append(current_streak)
            max_streak = max(max_streak, current_streak)
            
            return {
                'current_streak': current_streak,
                'longest_streak': max_streak,
                'average_streak': float(np.mean(streaks)) if streaks else 0,
                'total_streaks': len(streaks)
            }
            
        except Exception:
            return {}
    
    def _calculate_consistency_score(self, daily_counts: pd.Series) -> float:
        """Calculate a consistency score for writing habits"""
        try:
            if len(daily_counts) < 2:
                return 0.0
            
            # Higher score for more consistent writing
            cv = daily_counts.std() / daily_counts.mean() if daily_counts.mean() > 0 else 1
            consistency_score = max(0, 1 - cv)  # Inverse of coefficient of variation
            
            return float(consistency_score)
            
        except Exception:
            return 0.0
    
    def _calculate_emotional_balance(self, theme_counts: Dict[str, int]) -> float:
        """Calculate emotional balance score"""
        try:
            positive_emotions = theme_counts.get('happiness', 0) + theme_counts.get('gratitude', 0) + theme_counts.get('hope', 0)
            negative_emotions = theme_counts.get('anxiety', 0) + theme_counts.get('depression', 0) + theme_counts.get('anger', 0)
            
            total_emotions = positive_emotions + negative_emotions
            
            if total_emotions == 0:
                return 0.5  # Neutral
            
            balance = (positive_emotions / total_emotions)
            return float(balance)
            
        except Exception:
            return 0.5
    
    def _get_empty_writing_statistics(self) -> Dict[str, Any]:
        """Return empty writing statistics structure"""
        return {
            'total_entries': 0,
            'avg_content_length': 0,
            'avg_word_count': 0,
            'avg_title_length': 0,
            'min_content_length': 0,
            'max_content_length': 0,
            'total_words_written': 0,
            'content_length_std': 0,
            'writing_consistency': {'entries_per_week': 0, 'avg_days_between_entries': 0},
            'writing_depth_category': 'insufficient_data'
        }
    
    def _update_performance_metrics(self, start_time: float, records_processed: int):
        """Update performance tracking metrics"""
        import time
        try:
            self.collection_stats['total_collections'] += 1
            
            collection_time = time.time() - start_time
            total_collections = self.collection_stats['total_collections']
            
            # Update average collection time
            current_avg = self.collection_stats['avg_collection_time']
            new_avg = ((current_avg * (total_collections - 1)) + collection_time) / total_collections
            self.collection_stats['avg_collection_time'] = new_avg
            
        except Exception:
            pass  # Don't let metrics update failure affect the main process
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.collection_stats.copy()
    
    def clear_cache(self, user_id: Optional[int] = None):
        """Clear cache for specific user or all journaling data cache"""
        if user_id:
            for days in [7, 14, 30, 60, 90]:
                cache_key = f"journaling_data:{user_id}:{days}"
                cache.delete(cache_key)
        else:
            # Clear all journaling-related cache keys
            cache.delete_many([key for key in cache.keys() if key.startswith("journaling_data:")])


# Create singleton instance
journaling_service = JournalingCollectionService()

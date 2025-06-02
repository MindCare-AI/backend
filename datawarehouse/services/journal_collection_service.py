# datawarehouse/services/journal_collection_service.py
"""
Dedicated service for collecting and analyzing journaling data
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
import structlog
import re

logger = structlog.get_logger(__name__)
User = get_user_model()


@dataclass
class JournalAnalysisResult:
    """Result structure for journal analysis"""
    count: int
    total_words: int
    avg_content_length: float
    mood_improvement: float
    sentiment_analysis: Dict[str, Any]
    topic_analysis: Dict[str, Any]
    writing_frequency: Dict[str, Any]
    emotion_tracking: Dict[str, Any]
    therapeutic_themes: Dict[str, Any]
    entries: List[Dict[str, Any]]
    quality_score: float


class JournalCollectionService:
    """
    Specialized service for journal data collection and analysis
    
    Features:
    - Sentiment analysis and emotion tracking
    - Topic modeling and theme extraction
    - Writing frequency pattern analysis
    - Mood correlation analysis
    - Therapeutic progress tracking
    - Content quality assessment
    - Mental health insights generation
    """
    
    def __init__(self):
        self.collection_stats = {
            'total_collections': 0,
            'avg_processing_time': 0.0,
            'error_rate': 0.0
        }
        
        # Therapeutic keywords for theme detection
        self.therapeutic_themes = {
            'anxiety': ['anxious', 'worried', 'nervous', 'panic', 'stress', 'tension'],
            'depression': ['sad', 'depressed', 'hopeless', 'empty', 'down', 'blue'],
            'anger': ['angry', 'mad', 'furious', 'rage', 'irritated', 'frustrated'],
            'joy': ['happy', 'joyful', 'excited', 'cheerful', 'elated', 'content'],
            'gratitude': ['grateful', 'thankful', 'blessed', 'appreciate', 'grateful'],
            'relationships': ['family', 'friends', 'partner', 'relationship', 'social'],
            'work': ['work', 'job', 'career', 'office', 'colleagues', 'boss'],
            'self_care': ['exercise', 'meditation', 'sleep', 'healthy', 'wellness'],
            'therapy': ['therapy', 'therapist', 'counseling', 'session', 'treatment'],
            'goals': ['goal', 'achievement', 'progress', 'success', 'accomplish']
        }
    
    def collect_journal_data(self, user, start_date: datetime, end_date: datetime) -> JournalAnalysisResult:
        """
        Collect and analyze comprehensive journal data
        
        Args:
            user: User instance
            start_date: Start date for data collection
            end_date: End date for data collection
            
        Returns:
            JournalAnalysisResult with detailed analysis
        """
        try:
            from journal.models import JournalEntry
            
            # Get journal entries with all available fields
            entries = JournalEntry.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values(
                'id', 'title', 'content', 'mood_before', 'mood_after',
                'created_at', 'category_id', 'tags', 'is_private'
            ).order_by('created_at')
            
            if not entries:
                return self._get_empty_journal_analysis()
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(list(entries))
            df['created_at'] = pd.to_datetime(df['created_at'])
            df = df.sort_values('created_at')
            
            # Perform comprehensive analysis
            analysis_result = JournalAnalysisResult(
                count=len(df),
                total_words=self._calculate_total_words(df),
                avg_content_length=self._calculate_avg_content_length(df),
                mood_improvement=self._calculate_mood_improvement(df),
                sentiment_analysis=self._analyze_sentiment(df),
                topic_analysis=self._extract_topics(df),
                writing_frequency=self._analyze_writing_frequency(df),
                emotion_tracking=self._track_emotions(df),
                therapeutic_themes=self._analyze_therapeutic_themes(df),
                entries=df.to_dict('records'),
                quality_score=self._calculate_journal_quality_score(df)
            )
            
            logger.info("Journal data collection completed", 
                       user_id=user.id, 
                       entries_count=len(df),
                       total_words=analysis_result.total_words)
            
            return analysis_result
            
        except Exception as exc:
            logger.error("Error collecting journal data", error=str(exc), user_id=user.id)
            return self._get_empty_journal_analysis()
    
    def _calculate_total_words(self, df: pd.DataFrame) -> int:
        """Calculate total word count across all entries"""
        try:
            if df.empty or 'content' not in df:
                return 0
            
            total_words = 0
            for content in df['content'].dropna():
                if isinstance(content, str):
                    word_count = len(content.split())
                    total_words += word_count
            
            return total_words
            
        except Exception:
            return 0
    
    def _calculate_avg_content_length(self, df: pd.DataFrame) -> float:
        """Calculate average content length in words"""
        try:
            if df.empty or 'content' not in df:
                return 0.0
            
            word_counts = []
            for content in df['content'].dropna():
                if isinstance(content, str):
                    word_counts.append(len(content.split()))
            
            return float(np.mean(word_counts)) if word_counts else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_mood_improvement(self, df: pd.DataFrame) -> float:
        """Calculate overall mood improvement from before/after ratings"""
        try:
            if df.empty or 'mood_before' not in df or 'mood_after' not in df:
                return 0.0
            
            mood_changes = []
            for index, row in df.iterrows():
                if pd.notna(row['mood_before']) and pd.notna(row['mood_after']):
                    improvement = row['mood_after'] - row['mood_before']
                    mood_changes.append(improvement)
            
            return float(np.mean(mood_changes)) if mood_changes else 0.0
            
        except Exception:
            return 0.0
    
    def _analyze_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sentiment patterns in journal entries"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            # Simple sentiment analysis using keyword matching
            positive_words = [
                'happy', 'good', 'great', 'wonderful', 'amazing', 'excellent',
                'joy', 'excited', 'grateful', 'blessed', 'love', 'perfect',
                'successful', 'accomplished', 'proud', 'content', 'peaceful'
            ]
            
            negative_words = [
                'sad', 'bad', 'terrible', 'awful', 'horrible', 'depressed',
                'angry', 'frustrated', 'worried', 'anxious', 'stressed',
                'disappointed', 'lonely', 'tired', 'exhausted', 'overwhelmed'
            ]
            
            sentiment_scores = []
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            for content in df['content'].dropna():
                if not isinstance(content, str):
                    continue
                    
                content_lower = content.lower()
                pos_score = sum(1 for word in positive_words if word in content_lower)
                neg_score = sum(1 for word in negative_words if word in content_lower)
                
                if pos_score > neg_score:
                    sentiment = 'positive'
                    positive_count += 1
                    score = (pos_score - neg_score) / max(1, pos_score + neg_score)
                elif neg_score > pos_score:
                    sentiment = 'negative'
                    negative_count += 1
                    score = (neg_score - pos_score) / max(1, pos_score + neg_score) * -1
                else:
                    sentiment = 'neutral'
                    neutral_count += 1
                    score = 0
                
                sentiment_scores.append(score)
            
            avg_sentiment = float(np.mean(sentiment_scores)) if sentiment_scores else 0.0
            
            # Determine overall trend
            if avg_sentiment > 0.2:
                trend = 'predominantly_positive'
            elif avg_sentiment < -0.2:
                trend = 'predominantly_negative'
            else:
                trend = 'balanced'
            
            return {
                'average_sentiment_score': avg_sentiment,
                'sentiment_trend': trend,
                'positive_entries': positive_count,
                'negative_entries': negative_count,
                'neutral_entries': neutral_count,
                'sentiment_distribution': {
                    'positive': positive_count,
                    'negative': negative_count,
                    'neutral': neutral_count
                },
                'sentiment_consistency': float(np.std(sentiment_scores)) if len(sentiment_scores) > 1 else 0.0
            }
            
        except Exception:
            return {}
    
    def _extract_topics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract common topics and themes from journal content"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            # Simple topic extraction using keyword frequency
            all_words = []
            topic_mentions = {}
            
            # Common mental health and life topics
            topics = {
                'work': ['work', 'job', 'career', 'office', 'meeting', 'project'],
                'family': ['family', 'mom', 'dad', 'parent', 'sibling', 'relative'],
                'friends': ['friend', 'social', 'party', 'hangout', 'buddy'],
                'health': ['health', 'exercise', 'diet', 'medical', 'doctor', 'fitness'],
                'emotions': ['feel', 'emotion', 'mood', 'feeling', 'emotional'],
                'goals': ['goal', 'plan', 'dream', 'future', 'hope', 'ambition'],
                'challenges': ['problem', 'issue', 'difficult', 'challenge', 'struggle'],
                'relationships': ['relationship', 'partner', 'spouse', 'dating', 'love']
            }
            
            for content in df['content'].dropna():
                if not isinstance(content, str):
                    continue
                
                content_lower = content.lower()
                words = re.findall(r'\b\w+\b', content_lower)
                all_words.extend(words)
                
                # Count topic mentions
                for topic, keywords in topics.items():
                    mentions = sum(1 for keyword in keywords if keyword in content_lower)
                    if topic not in topic_mentions:
                        topic_mentions[topic] = 0
                    topic_mentions[topic] += mentions
            
            # Get most common words (excluding common stop words)
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
                'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was',
                'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
                'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
                'can', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'myself',
                'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
                'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
                'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves'
            }
            
            filtered_words = [word for word in all_words if word not in stop_words and len(word) > 2]
            word_freq = pd.Series(filtered_words).value_counts()
            
            return {
                'total_unique_words': len(set(all_words)),
                'topic_mentions': topic_mentions,
                'most_discussed_topic': max(topic_mentions.items(), key=lambda x: x[1], default=(None, 0))[0],
                'top_keywords': dict(word_freq.head(10)),
                'vocabulary_richness': len(set(all_words)) / max(1, len(all_words)),
                'avg_words_per_entry': len(all_words) / max(1, len(df))
            }
            
        except Exception:
            return {}
    
    def _analyze_writing_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze writing frequency patterns and consistency"""
        try:
            if df.empty or 'created_at' not in df:
                return {}
            
            df['date'] = pd.to_datetime(df['created_at']).dt.date
            df['hour'] = pd.to_datetime(df['created_at']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['created_at']).dt.day_name()
            
            # Daily writing counts
            daily_counts = df.groupby('date').size()
            
            # Hour distribution
            hour_distribution = df['hour'].value_counts().to_dict()
            
            # Day of week distribution
            dow_distribution = df['day_of_week'].value_counts().to_dict()
            
            # Calculate consistency metrics
            writing_streak = self._calculate_writing_streak(df)
            
            return {
                'avg_entries_per_day': float(daily_counts.mean()) if not daily_counts.empty else 0.0,
                'max_entries_per_day': int(daily_counts.max()) if not daily_counts.empty else 0,
                'total_writing_days': len(daily_counts),
                'writing_consistency': float(daily_counts.std()) if len(daily_counts) > 1 else 0.0,
                'preferred_writing_hours': hour_distribution,
                'day_of_week_patterns': dow_distribution,
                'most_active_hour': max(hour_distribution.items(), key=lambda x: x[1], default=(None, 0))[0],
                'most_active_day': max(dow_distribution.items(), key=lambda x: x[1], default=(None, 0))[0],
                'current_writing_streak': writing_streak,
                'writing_regularity_score': self._calculate_regularity_score(daily_counts)
            }
            
        except Exception:
            return {}
    
    def _track_emotions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Track emotional patterns and evolution over time"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            # Define emotion keywords
            emotions = {
                'happiness': ['happy', 'joy', 'cheerful', 'elated', 'excited', 'pleased'],
                'sadness': ['sad', 'depressed', 'melancholy', 'sorrowful', 'blue', 'down'],
                'anxiety': ['anxious', 'worried', 'nervous', 'tense', 'uneasy', 'restless'],
                'anger': ['angry', 'mad', 'furious', 'irritated', 'annoyed', 'frustrated'],
                'fear': ['afraid', 'scared', 'terrified', 'fearful', 'panicked', 'frightened'],
                'love': ['love', 'affection', 'care', 'adore', 'cherish', 'devoted'],
                'gratitude': ['grateful', 'thankful', 'appreciative', 'blessed', 'fortunate'],
                'hope': ['hopeful', 'optimistic', 'confident', 'positive', 'encouraging']
            }
            
            emotion_timeline = []
            emotion_counts = {emotion: 0 for emotion in emotions.keys()}
            
            for index, row in df.iterrows():
                if pd.isna(row['content']) or not isinstance(row['content'], str):
                    continue
                
                content_lower = row['content'].lower()
                entry_emotions = []
                
                for emotion, keywords in emotions.items():
                    count = sum(1 for keyword in keywords if keyword in content_lower)
                    if count > 0:
                        emotion_counts[emotion] += count
                        entry_emotions.append(emotion)
                
                emotion_timeline.append({
                    'date': row['created_at'],
                    'emotions': entry_emotions,
                    'dominant_emotion': max([(e, sum(1 for k in emotions[e] if k in content_lower)) 
                                           for e in emotions.keys()], 
                                           key=lambda x: x[1], default=(None, 0))[0]
                })
            
            # Calculate emotional diversity
            total_emotion_mentions = sum(emotion_counts.values())
            emotion_distribution = {
                emotion: count / max(1, total_emotion_mentions) 
                for emotion, count in emotion_counts.items()
            }
            
            return {
                'emotion_counts': emotion_counts,
                'emotion_distribution': emotion_distribution,
                'dominant_emotion': max(emotion_counts.items(), key=lambda x: x[1], default=(None, 0))[0],
                'emotional_diversity': len([e for e, c in emotion_counts.items() if c > 0]),
                'emotion_timeline': emotion_timeline[-10:],  # Last 10 entries
                'emotional_balance_score': self._calculate_emotional_balance(emotion_counts)
            }
            
        except Exception:
            return {}
    
    def _analyze_therapeutic_themes(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze therapeutic themes and mental health indicators"""
        try:
            if df.empty or 'content' not in df:
                return {}
            
            theme_counts = {theme: 0 for theme in self.therapeutic_themes.keys()}
            theme_evolution = []
            
            for index, row in df.iterrows():
                if pd.isna(row['content']) or not isinstance(row['content'], str):
                    continue
                
                content_lower = row['content'].lower()
                entry_themes = []
                
                for theme, keywords in self.therapeutic_themes.items():
                    count = sum(1 for keyword in keywords if keyword in content_lower)
                    if count > 0:
                        theme_counts[theme] += count
                        entry_themes.append(theme)
                
                theme_evolution.append({
                    'date': row['created_at'],
                    'themes': entry_themes,
                    'primary_theme': max([(t, sum(1 for k in self.therapeutic_themes[t] if k in content_lower)) 
                                        for t in self.therapeutic_themes.keys()], 
                                        key=lambda x: x[1], default=(None, 0))[0]
                })
            
            # Calculate therapeutic progress indicators
            positive_themes = ['joy', 'gratitude', 'self_care', 'goals']
            negative_themes = ['anxiety', 'depression', 'anger']
            
            positive_mentions = sum(theme_counts[theme] for theme in positive_themes if theme in theme_counts)
            negative_mentions = sum(theme_counts[theme] for theme in negative_themes if theme in theme_counts)
            
            therapeutic_balance = (positive_mentions - negative_mentions) / max(1, positive_mentions + negative_mentions)
            
            return {
                'theme_counts': theme_counts,
                'primary_theme': max(theme_counts.items(), key=lambda x: x[1], default=(None, 0))[0],
                'positive_theme_mentions': positive_mentions,
                'negative_theme_mentions': negative_mentions,
                'therapeutic_balance_score': float(therapeutic_balance),
                'theme_diversity': len([t for t, c in theme_counts.items() if c > 0]),
                'therapy_engagement_indicators': {
                    'mentions_therapy': theme_counts.get('therapy', 0),
                    'self_care_focus': theme_counts.get('self_care', 0),
                    'goal_orientation': theme_counts.get('goals', 0)
                },
                'theme_evolution': theme_evolution[-5:]  # Last 5 entries
            }
            
        except Exception:
            return {}
    
    def _calculate_writing_streak(self, df: pd.DataFrame) -> int:
        """Calculate current writing streak in days"""
        try:
            if df.empty or 'created_at' not in df:
                return 0
            
            # Get unique writing dates
            writing_dates = sorted(pd.to_datetime(df['created_at']).dt.date.unique(), reverse=True)
            
            if not writing_dates:
                return 0
            
            # Check if today or yesterday was a writing day
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            if writing_dates[0] not in [today, yesterday]:
                return 0
            
            # Count consecutive days
            streak = 1
            current_date = writing_dates[0]
            
            for i in range(1, len(writing_dates)):
                expected_date = current_date - timedelta(days=1)
                if writing_dates[i] == expected_date:
                    streak += 1
                    current_date = writing_dates[i]
                else:
                    break
            
            return streak
            
        except Exception:
            return 0
    
    def _calculate_regularity_score(self, daily_counts: pd.Series) -> float:
        """Calculate writing regularity score (0-1)"""
        try:
            if daily_counts.empty:
                return 0.0
            
            # Calculate coefficient of variation (lower is more regular)
            mean_count = daily_counts.mean()
            std_count = daily_counts.std()
            
            if mean_count == 0:
                return 0.0
            
            cv = std_count / mean_count
            # Convert to 0-1 score where 1 is most regular
            regularity_score = max(0, 1 - cv)
            
            return float(regularity_score)
            
        except Exception:
            return 0.0
    
    def _calculate_emotional_balance(self, emotion_counts: Dict[str, int]) -> float:
        """Calculate emotional balance score"""
        try:
            positive_emotions = ['happiness', 'love', 'gratitude', 'hope']
            negative_emotions = ['sadness', 'anxiety', 'anger', 'fear']
            
            positive_count = sum(emotion_counts.get(emotion, 0) for emotion in positive_emotions)
            negative_count = sum(emotion_counts.get(emotion, 0) for emotion in negative_emotions)
            
            total_count = positive_count + negative_count
            
            if total_count == 0:
                return 0.5  # Neutral balance
            
            balance_score = positive_count / total_count
            return float(balance_score)
            
        except Exception:
            return 0.5
    
    def _calculate_journal_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate overall journal quality score"""
        try:
            if df.empty:
                return 0.0
            
            quality_factors = []
            
            # Content length consistency (not too short, not extremely long)
            if 'content' in df:
                word_counts = [len(str(content).split()) for content in df['content'].dropna()]
                if word_counts:
                    avg_words = np.mean(word_counts)
                    # Optimal range: 50-500 words
                    length_score = min(1.0, max(0.0, (avg_words - 10) / 40)) if avg_words < 50 else min(1.0, max(0.5, 1 - (avg_words - 500) / 1000))
                    quality_factors.append(length_score)
            
            # Frequency consistency
            if 'created_at' in df:
                df['date'] = pd.to_datetime(df['created_at']).dt.date
                daily_counts = df.groupby('date').size()
                frequency_score = min(1.0, len(daily_counts) / 7)  # Writing at least weekly
                quality_factors.append(frequency_score)
            
            # Emotional expression diversity
            emotion_diversity = self._track_emotions(df).get('emotional_diversity', 0)
            emotion_score = min(1.0, emotion_diversity / 4)  # Up to 4 different emotions
            quality_factors.append(emotion_score)
            
            # Mood tracking completion
            if 'mood_before' in df and 'mood_after' in df:
                mood_completion = (df['mood_before'].notna() & df['mood_after'].notna()).sum() / len(df)
                quality_factors.append(mood_completion)
            
            return float(np.mean(quality_factors)) if quality_factors else 0.0
            
        except Exception:
            return 0.5
    
    def _get_empty_journal_analysis(self) -> JournalAnalysisResult:
        """Return empty journal analysis result"""
        return JournalAnalysisResult(
            count=0,
            total_words=0,
            avg_content_length=0.0,
            mood_improvement=0.0,
            sentiment_analysis={},
            topic_analysis={},
            writing_frequency={},
            emotion_tracking={},
            therapeutic_themes={},
            entries=[],
            quality_score=0.0
        )
    
    def get_journal_insights(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Generate actionable insights from journal data
        
        Args:
            user: User instance
            days: Number of days to analyze
            
        Returns:
            Dict with journal insights and recommendations
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            journal_result = self.collect_journal_data(user, start_date, end_date)
            
            if journal_result.count == 0:
                return {'insights_available': False, 'reason': 'no_data'}
            
            insights = []
            recommendations = []
            
            # Writing frequency insights
            writing_freq = journal_result.writing_frequency
            if writing_freq.get('current_writing_streak', 0) > 7:
                insights.append(f"Great job! You have a {writing_freq['current_writing_streak']}-day writing streak.")
            elif writing_freq.get('avg_entries_per_day', 0) < 0.3:
                recommendations.append("Try to write in your journal more regularly for better mental health tracking")
            
            # Sentiment insights
            sentiment = journal_result.sentiment_analysis
            if sentiment.get('sentiment_trend') == 'predominantly_positive':
                insights.append("Your journal entries show a predominantly positive emotional tone")
            elif sentiment.get('sentiment_trend') == 'predominantly_negative':
                insights.append("Your recent journal entries show some concerning patterns. Consider discussing with your therapist")
                recommendations.append("Focus on writing about positive experiences and gratitude")
            
            # Therapeutic themes insights
            themes = journal_result.therapeutic_themes
            if themes.get('therapeutic_balance_score', 0) > 0.2:
                insights.append("Your journal shows good balance between processing challenges and celebrating positives")
            elif themes.get('therapy_engagement_indicators', {}).get('mentions_therapy', 0) > 0:
                insights.append("You're actively engaging with therapeutic concepts in your writing")
            
            # Mood improvement insights
            if journal_result.mood_improvement > 0.5:
                insights.append("Your journal writing sessions are consistently improving your mood")
                recommendations.append("Continue your current journaling practice - it's working well for you")
            elif journal_result.mood_improvement < -0.5:
                recommendations.append("Consider discussing your journaling topics with your therapist")
            
            # Quality insights
            if journal_result.quality_score > 0.8:
                insights.append("You're maintaining excellent journaling practices!")
            elif journal_result.quality_score < 0.4:
                recommendations.append("Try to write longer, more detailed entries for better therapeutic benefit")
            
            return {
                'insights_available': True,
                'insights': insights,
                'recommendations': recommendations,
                'analysis_summary': {
                    'period_days': days,
                    'entries_count': journal_result.count,
                    'total_words': journal_result.total_words,
                    'avg_words_per_entry': journal_result.avg_content_length,
                    'mood_improvement': journal_result.mood_improvement,
                    'quality_score': journal_result.quality_score
                }
            }
            
        except Exception as exc:
            logger.error("Error generating journal insights", error=str(exc), user_id=user.id)
            return {'insights_available': False, 'error': str(exc)}


# Create singleton instance
journal_collector = JournalCollectionService()

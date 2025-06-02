# datawarehouse/services/data_collection.py
"""
Enterprise-Grade Centralized Data Collection Service for MindCare AI Engine
Uses modern Python tools for high-performance data processing and specialized collection services
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
try:
    import orjson as json
except ImportError:
    import json as json
from pydantic import BaseModel, Field, validator
try:
    import polars as pl
except ImportError:
    pl = None
from scipy import stats

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
    
    @validator('max_workers')
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
    """Structured representation of user data using specialized services"""
    user_id: int
    collection_date: datetime
    period_days: int
    
    # Data from specialized services
    user_behavior_snapshot: Optional[Dict[str, Any]] = None
    mood_journal_snapshot: Optional[Dict[str, Any]] = None  
    therapist_session_snapshot: Optional[Dict[str, Any]] = None
    feeds_snapshot: Optional[Dict[str, Any]] = None
    
    # Legacy data structure for backwards compatibility
    mood_data: Optional[Dict[str, Any]] = None
    journal_data: Optional[Dict[str, Any]] = None
    messaging_data: Optional[Dict[str, Any]] = None
    appointment_data: Optional[Dict[str, Any]] = None
    notification_data: Optional[Dict[str, Any]] = None
    analytics_data: Optional[Dict[str, Any]] = None
    social_data: Optional[Dict[str, Any]] = None
    
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values for None fields"""
        if self.metadata is None:
            self.metadata = {}
        
        # Initialize legacy data if None
        for field in ['mood_data', 'journal_data', 'messaging_data', 
                     'appointment_data', 'notification_data', 'analytics_data', 'social_data']:
            if getattr(self, field) is None:
                setattr(self, field, {})
                
        # Initialize specialized service snapshots if None
        for field in ['user_behavior_snapshot', 'mood_journal_snapshot', 
                     'therapist_session_snapshot', 'feeds_snapshot']:
            if getattr(self, field) is None:
                setattr(self, field, {})


class DataCollectionService:
    """
    Enterprise-grade data collection service using modern Python tools and specialized services
    
    Features:
    - Integration with specialized collection services for different data domains
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
        
        # Initialize specialized collection services
        self._initialize_specialized_services()
        
        # Performance tracking
        self.collection_stats = {
            'total_collections': 0,
            'avg_collection_time': 0.0,
            'error_rate': 0.0,
            'cache_hit_rate': 0.0
        }
        
    def _initialize_specialized_services(self):
        """Initialize specialized collection services"""
        try:
            # Import and initialize specialized services
            from .therapist_session_notes_service import TherapistSessionNotesCollectionService
            from .feeds_service import FeedsCollectionService
            
            self.therapist_service = TherapistSessionNotesCollectionService()
            self.feeds_service = FeedsCollectionService()
            
            # Initialize other services if they exist
            try:
                from .mood_tracking_service import MoodTrackingCollectionService
                self.mood_service = MoodTrackingCollectionService()
            except ImportError:
                self.mood_service = None
                logger.warning("MoodTrackingCollectionService not found, using legacy mood collection")
                
            try:
                from .journaling_service import JournalingCollectionService
                self.journal_service = JournalingCollectionService()
            except ImportError:
                self.journal_service = None
                logger.warning("JournalingCollectionService not found, using legacy journal collection")
                
            logger.info("Specialized collection services initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing specialized services: {str(e)}")
            # Fallback to legacy collection methods
            self.therapist_service = None
            self.feeds_service = None
            self.mood_service = None
            self.journal_service = None
        
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
                self.collection_stats['cache_hit_rate'] += 1
                return UserDataSnapshot(**cached_data)
            
            # Get user object
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError(f"User {user_id} not found")
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Collect data using both specialized services and legacy methods
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {}
                
                # Submit specialized service collection tasks
                if self.therapist_service:
                    futures[executor.submit(
                        self._collect_with_therapist_service, user, days
                    )] = 'therapist_service'
                    
                if self.feeds_service:
                    futures[executor.submit(
                        self._collect_with_feeds_service, user, days
                    )] = 'feeds_service'
                    
                if self.mood_service:
                    futures[executor.submit(
                        self._collect_with_mood_service, user, days
                    )] = 'mood_service'
                    
                if self.journal_service:
                    futures[executor.submit(
                        self._collect_with_journal_service, user, days
                    )] = 'journal_service'
                
                # Submit legacy collection tasks for data not covered by specialized services
                futures.update({
                    executor.submit(self._collect_messaging_data, user, start_date, end_date): 'messaging',
                    executor.submit(self._collect_appointment_data, user, start_date, end_date): 'appointment',
                    executor.submit(self._collect_notification_data, user, start_date, end_date): 'notification',
                    executor.submit(self._collect_analytics_data, user, start_date, end_date): 'analytics',
                })
                
                # Add legacy mood/journal collection if specialized services not available
                if not self.mood_service:
                    futures[executor.submit(self._collect_mood_data, user, start_date, end_date)] = 'mood'
                if not self.journal_service:
                    futures[executor.submit(self._collect_journal_data, user, start_date, end_date)] = 'journal'
                if not self.feeds_service:
                    futures[executor.submit(self._collect_social_data, user, start_date, end_date)] = 'social'
                
                # Collect results
                results = {}
                specialized_snapshots = {}
                errors = []
                
                for future in as_completed(futures):
                    data_type = futures[future]
                    try:
                        result = future.result()
                        
                        # Handle specialized service results differently
                        if data_type.endswith('_service'):
                            specialized_snapshots[data_type] = result
                        else:
                            results[f"{data_type}_data"] = result
                            
                    except Exception as e:
                        logger.error(f"Error collecting {data_type} data", error=str(e))
                        errors.append(f"{data_type}: {str(e)}")
                        
                        if data_type.endswith('_service'):
                            specialized_snapshots[data_type] = {}
                        else:
                            results[f"{data_type}_data"] = {}
            
            # Create snapshot with both legacy and specialized service data
            snapshot = UserDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                
                # Specialized service snapshots
                therapist_session_snapshot=specialized_snapshots.get('therapist_service', {}),
                feeds_snapshot=specialized_snapshots.get('feeds_service', {}),
                mood_journal_snapshot=specialized_snapshots.get('mood_service', {}),
                
                # Legacy data for backwards compatibility
                mood_data=results.get('mood_data', {}),
                journal_data=results.get('journal_data', {}),
                messaging_data=results.get('messaging_data', {}),
                appointment_data=results.get('appointment_data', {}),
                notification_data=results.get('notification_data', {}),
                analytics_data=results.get('analytics_data', {}),
                social_data=results.get('social_data', {}),
                
                metadata={
                    'collection_time': time.time() - start_time,
                    'errors': errors,
                    'data_sources': list(results.keys()),
                    'specialized_services': list(specialized_snapshots.keys()),
                    'version': '3.0'  # Updated version to reflect new architecture
                }
            )
            
            # Cache the results
            cache.set(cache_key, asdict(snapshot), self.config.cache_timeout)
            
            # Update performance metrics
            self._update_performance_metrics(start_time, len(results), errors)
            
            logger.info("Data collection completed", 
                       user_id=user_id, 
                       collection_time=time.time() - start_time,
                       data_sources=len(results))
            
            return snapshot
            
        except Exception as e:
            logger.error("Data collection failed", user_id=user_id, error=str(e))
            raise
    
    def _collect_mood_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and process mood data using pandas for efficiency"""
        try:
            # Import here to avoid circular imports
            from mood.models import MoodLog
            
            # Get mood logs
            mood_logs = MoodLog.objects.filter(
                user=user,
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'mood_score', 'energy_level', 'sleep_hours', 
                'stress_level', 'notes', 'timestamp', 'activities'
            )
            
            if not mood_logs:
                return {
                    'count': 0,
                    'avg_mood': None,
                    'trend': 'stable',
                    'volatility': 0.0,
                    'entries': []
                }
            
            # Convert to pandas DataFrame for analysis
            df = pd.DataFrame(list(mood_logs))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate statistics
            mood_scores = df['mood_score'].dropna()
            
            analysis = {
                'count': len(df),
                'avg_mood': float(mood_scores.mean()) if not mood_scores.empty else None,
                'min_mood': float(mood_scores.min()) if not mood_scores.empty else None,
                'max_mood': float(mood_scores.max()) if not mood_scores.empty else None,
                'volatility': float(mood_scores.std()) if len(mood_scores) > 1 else 0.0,
                'trend': self._calculate_trend(mood_scores.values),
                'daily_averages': self._calculate_daily_averages(df),
                'activity_patterns': self._analyze_activity_patterns(df),
                'entries': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting mood data", error=str(e))
            return {'error': str(e), 'count': 0, 'entries': []}
    
    def _collect_journal_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and analyze journal data"""
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
                return {
                    'count': 0,
                    'sentiment_trend': 'neutral',
                    'topics': [],
                    'entries': []
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(list(entries))
            
            # Analyze content
            analysis = {
                'count': len(df),
                'avg_content_length': float(df['content'].str.len().mean()) if not df.empty else 0.0,
                'mood_improvement': self._calculate_mood_improvement(df),
                'sentiment_analysis': self._analyze_journal_sentiment(df),
                'topic_analysis': self._extract_journal_topics(df),
                'writing_frequency': self._analyze_writing_frequency(df),
                'entries': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting journal data", error=str(e))
            return {'error': str(e), 'count': 0, 'entries': []}
    
    def _collect_messaging_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect messaging/communication data"""
        try:
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage
            
            # Get one-to-one messages
            one_to_one_msgs = OneToOneMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'content', 'sender_id', 'timestamp', 'conversation_id'
            )
            
            # Get group messages  
            group_msgs = GroupMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'content', 'sender_id', 'timestamp', 'conversation_id'
            )
            
            all_messages = list(one_to_one_msgs) + list(group_msgs)
            
            if not all_messages:
                return {
                    'count': 0,
                    'sent_count': 0,
                    'received_count': 0,
                    'avg_message_length': 0.0,
                    'communication_frequency': {},
                    'messages': []
                }
            
            df = pd.DataFrame(all_messages)
            user_sent = df[df['sender_id'] == user.id]
            user_received = df[df['sender_id'] != user.id]
            
            analysis = {
                'count': len(df),
                'sent_count': len(user_sent),
                'received_count': len(user_received),
                'avg_message_length': float(df['content'].str.len().mean()) if not df.empty else 0.0,
                'communication_frequency': self._analyze_communication_frequency(df),
                'sentiment_patterns': self._analyze_message_sentiment(df),
                'messages': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting messaging data", error=str(e))
            return {'error': str(e), 'count': 0, 'messages': []}
    
    def _collect_appointment_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect appointment data"""
        try:
            from appointments.models import Appointment
            
            appointments = Appointment.objects.filter(
                Q(patient=user) | Q(therapist=user),
                appointment_date__range=(start_date, end_date)
            ).values(
                'id', 'appointment_date', 'status', 'type', 'notes',
                'patient_id', 'therapist_id', 'duration'
            )
            
            if not appointments:
                return {
                    'count': 0,
                    'completed_count': 0,
                    'cancelled_count': 0,
                    'upcoming_count': 0,
                    'appointments': []
                }
            
            df = pd.DataFrame(list(appointments))
            
            analysis = {
                'count': len(df),
                'completed_count': len(df[df['status'] == 'completed']),
                'cancelled_count': len(df[df['status'] == 'cancelled']),
                'upcoming_count': len(df[df['status'] == 'scheduled']),
                'attendance_rate': self._calculate_attendance_rate(df),
                'appointment_frequency': self._analyze_appointment_frequency(df),
                'appointments': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting appointment data", error=str(e))
            return {'error': str(e), 'count': 0, 'appointments': []}
    
    def _collect_notification_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect notification data"""
        try:
            from notifications.models import Notification
            
            notifications = Notification.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values(
                'id', 'notification_type', 'title', 'message', 
                'is_read', 'created_at', 'read_at'
            )
            
            if not notifications:
                return {
                    'count': 0,
                    'read_count': 0,
                    'unread_count': 0,
                    'notifications': []
                }
            
            df = pd.DataFrame(list(notifications))
            
            analysis = {
                'count': len(df),
                'read_count': len(df[df['is_read']]),
                'unread_count': len(df[~df['is_read']]),
                'read_rate': len(df[df['is_read']]) / len(df) if len(df) > 0 else 0.0,
                'notification_types': df['notification_type'].value_counts().to_dict(),
                'notifications': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting notification data", error=str(e))
            return {'error': str(e), 'count': 0, 'notifications': []}
    
    def _collect_analytics_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect analytics data"""
        try:
            from analytics.models import UserAnalytics
            
            analytics = UserAnalytics.objects.filter(
                user=user,
                date__range=(start_date.date(), end_date.date())
            ).values(
                'date', 'sessions_count', 'total_time_spent',
                'features_used', 'goals_completed'
            )
            
            if not analytics:
                return {
                    'count': 0,
                    'total_sessions': 0,
                    'avg_session_time': 0.0,
                    'analytics': []
                }
            
            df = pd.DataFrame(list(analytics))
            
            analysis = {
                'count': len(df),
                'total_sessions': int(df['sessions_count'].sum()) if not df.empty else 0,
                'avg_session_time': float(df['total_time_spent'].mean()) if not df.empty else 0.0,
                'most_used_features': self._analyze_feature_usage(df),
                'engagement_trend': self._calculate_engagement_trend(df),
                'analytics': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting analytics data", error=str(e))
            return {'error': str(e), 'count': 0, 'analytics': []}
    
    def _collect_social_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect social/feeds data"""
        try:
            from feeds.models import Post, Comment, Like
            
            # Get user's posts
            posts = Post.objects.filter(
                author=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'content', 'created_at', 'likes_count', 'comments_count')
            
            # Get user's comments
            comments = Comment.objects.filter(
                author=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'content', 'created_at', 'post_id')
            
            # Get user's likes
            likes = Like.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'created_at', 'post_id')
            
            analysis = {
                'posts_count': len(posts),
                'comments_count': len(comments),
                'likes_count': len(likes),
                'social_engagement': self._calculate_social_engagement(posts, comments, likes),
                'posts': list(posts),
                'comments': list(comments),
                'likes': list(likes)
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting social data", error=str(e))
            return {'error': str(e), 'posts_count': 0, 'comments_count': 0, 'likes_count': 0}
    
    # Specialized Service Collection Methods
    
    def _collect_with_therapist_service(self, user, days: int) -> Dict[str, Any]:
        """Collect data using the specialized therapist session notes service"""
        try:
            if self.therapist_service:
                snapshot = self.therapist_service.collect_therapist_session_data(user, days)
                return asdict(snapshot) if snapshot else {}
            return {}
        except Exception as e:
            logger.error(f"Error in therapist service collection: {str(e)}")
            return {}
    
    def _collect_with_feeds_service(self, user, days: int) -> Dict[str, Any]:
        """Collect data using the specialized feeds service"""
        try:
            if self.feeds_service:
                snapshot = self.feeds_service.collect_feeds_data(user, days)
                return asdict(snapshot) if snapshot else {}
            return {}
        except Exception as e:
            logger.error(f"Error in feeds service collection: {str(e)}")
            return {}
    
    def _collect_with_mood_service(self, user, days: int) -> Dict[str, Any]:
        """Collect data using the specialized mood tracking service"""
        try:
            if self.mood_service:
                # Assuming mood service has a similar interface
                snapshot = self.mood_service.collect_mood_data(user, days)
                return asdict(snapshot) if snapshot else {}
            return {}
        except Exception as e:
            logger.error(f"Error in mood service collection: {str(e)}")
            return {}
    
    def _collect_with_journal_service(self, user, days: int) -> Dict[str, Any]:
        """Collect data using the specialized journaling service"""
        try:
            if self.journal_service:
                # Assuming journal service has a similar interface
                snapshot = self.journal_service.collect_journal_data(user, days)
                return asdict(snapshot) if snapshot else {}
            return {}
        except Exception as e:
            logger.error(f"Error in journal service collection: {str(e)}")
            return {}
    
    # Legacy Collection Methods (for backwards compatibility and services not yet modularized)
    
    def _collect_mood_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and process mood data using pandas for efficiency"""
        try:
            # Import here to avoid circular imports
            from mood.models import MoodLog
            
            # Get mood logs
            mood_logs = MoodLog.objects.filter(
                user=user,
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'mood_score', 'energy_level', 'sleep_hours', 
                'stress_level', 'notes', 'timestamp', 'activities'
            )
            
            if not mood_logs:
                return {
                    'count': 0,
                    'avg_mood': None,
                    'trend': 'stable',
                    'volatility': 0.0,
                    'entries': []
                }
            
            # Convert to pandas DataFrame for analysis
            df = pd.DataFrame(list(mood_logs))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate statistics
            mood_scores = df['mood_score'].dropna()
            
            analysis = {
                'count': len(df),
                'avg_mood': float(mood_scores.mean()) if not mood_scores.empty else None,
                'min_mood': float(mood_scores.min()) if not mood_scores.empty else None,
                'max_mood': float(mood_scores.max()) if not mood_scores.empty else None,
                'volatility': float(mood_scores.std()) if len(mood_scores) > 1 else 0.0,
                'trend': self._calculate_trend(mood_scores.values),
                'daily_averages': self._calculate_daily_averages(df),
                'activity_patterns': self._analyze_activity_patterns(df),
                'entries': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting mood data", error=str(e))
            return {'error': str(e), 'count': 0, 'entries': []}
    
    def _collect_journal_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and analyze journal data"""
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
                return {
                    'count': 0,
                    'sentiment_trend': 'neutral',
                    'topics': [],
                    'entries': []
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(list(entries))
            
            # Analyze content
            analysis = {
                'count': len(df),
                'avg_content_length': float(df['content'].str.len().mean()) if not df.empty else 0.0,
                'mood_improvement': self._calculate_mood_improvement(df),
                'sentiment_analysis': self._analyze_journal_sentiment(df),
                'topic_analysis': self._extract_journal_topics(df),
                'writing_frequency': self._analyze_writing_frequency(df),
                'entries': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting journal data", error=str(e))
            return {'error': str(e), 'count': 0, 'entries': []}
    
    def _collect_messaging_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect messaging/communication data"""
        try:
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage
            
            # Get one-to-one messages
            one_to_one_msgs = OneToOneMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'content', 'sender_id', 'timestamp', 'conversation_id'
            )
            
            # Get group messages  
            group_msgs = GroupMessage.objects.filter(
                Q(sender=user) | Q(conversation__participants=user),
                timestamp__range=(start_date, end_date)
            ).values(
                'id', 'content', 'sender_id', 'timestamp', 'conversation_id'
            )
            
            all_messages = list(one_to_one_msgs) + list(group_msgs)
            
            if not all_messages:
                return {
                    'count': 0,
                    'sent_count': 0,
                    'received_count': 0,
                    'avg_message_length': 0.0,
                    'communication_frequency': {},
                    'messages': []
                }
            
            df = pd.DataFrame(all_messages)
            user_sent = df[df['sender_id'] == user.id]
            user_received = df[df['sender_id'] != user.id]
            
            analysis = {
                'count': len(df),
                'sent_count': len(user_sent),
                'received_count': len(user_received),
                'avg_message_length': float(df['content'].str.len().mean()) if not df.empty else 0.0,
                'communication_frequency': self._analyze_communication_frequency(df),
                'sentiment_patterns': self._analyze_message_sentiment(df),
                'messages': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting messaging data", error=str(e))
            return {'error': str(e), 'count': 0, 'messages': []}
    
    def _collect_appointment_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect appointment data"""
        try:
            from appointments.models import Appointment
            
            appointments = Appointment.objects.filter(
                Q(patient=user) | Q(therapist=user),
                appointment_date__range=(start_date, end_date)
            ).values(
                'id', 'appointment_date', 'status', 'type', 'notes',
                'patient_id', 'therapist_id', 'duration'
            )
            
            if not appointments:
                return {
                    'count': 0,
                    'completed_count': 0,
                    'cancelled_count': 0,
                    'upcoming_count': 0,
                    'appointments': []
                }
            
            df = pd.DataFrame(list(appointments))
            
            analysis = {
                'count': len(df),
                'completed_count': len(df[df['status'] == 'completed']),
                'cancelled_count': len(df[df['status'] == 'cancelled']),
                'upcoming_count': len(df[df['status'] == 'scheduled']),
                'attendance_rate': self._calculate_attendance_rate(df),
                'appointment_frequency': self._analyze_appointment_frequency(df),
                'appointments': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting appointment data", error=str(e))
            return {'error': str(e), 'count': 0, 'appointments': []}
    
    def _collect_notification_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect notification data"""
        try:
            from notifications.models import Notification
            
            notifications = Notification.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values(
                'id', 'notification_type', 'title', 'message', 
                'is_read', 'created_at', 'read_at'
            )
            
            if not notifications:
                return {
                    'count': 0,
                    'read_count': 0,
                    'unread_count': 0,
                    'notifications': []
                }
            
            df = pd.DataFrame(list(notifications))
            
            analysis = {
                'count': len(df),
                'read_count': len(df[df['is_read']]),
                'unread_count': len(df[~df['is_read']]),
                'read_rate': len(df[df['is_read']]) / len(df) if len(df) > 0 else 0.0,
                'notification_types': df['notification_type'].value_counts().to_dict(),
                'notifications': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting notification data", error=str(e))
            return {'error': str(e), 'count': 0, 'notifications': []}
    
    def _collect_analytics_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect analytics data"""
        try:
            from analytics.models import UserAnalytics
            
            analytics = UserAnalytics.objects.filter(
                user=user,
                date__range=(start_date.date(), end_date.date())
            ).values(
                'date', 'sessions_count', 'total_time_spent',
                'features_used', 'goals_completed'
            )
            
            if not analytics:
                return {
                    'count': 0,
                    'total_sessions': 0,
                    'avg_session_time': 0.0,
                    'analytics': []
                }
            
            df = pd.DataFrame(list(analytics))
            
            analysis = {
                'count': len(df),
                'total_sessions': int(df['sessions_count'].sum()) if not df.empty else 0,
                'avg_session_time': float(df['total_time_spent'].mean()) if not df.empty else 0.0,
                'most_used_features': self._analyze_feature_usage(df),
                'engagement_trend': self._calculate_engagement_trend(df),
                'analytics': df.to_dict('records')
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting analytics data", error=str(e))
            return {'error': str(e), 'count': 0, 'analytics': []}
    
    def _collect_social_data(self, user, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect social/feeds data"""
        try:
            from feeds.models import Post, Comment, Like
            
            # Get user's posts
            posts = Post.objects.filter(
                author=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'content', 'created_at', 'likes_count', 'comments_count')
            
            # Get user's comments
            comments = Comment.objects.filter(
                author=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'content', 'created_at', 'post_id')
            
            # Get user's likes
            likes = Like.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).values('id', 'created_at', 'post_id')
            
            analysis = {
                'posts_count': len(posts),
                'comments_count': len(comments),
                'likes_count': len(likes),
                'social_engagement': self._calculate_social_engagement(posts, comments, likes),
                'posts': list(posts),
                'comments': list(comments),
                'likes': list(likes)
            }
            
            return analysis
            
        except Exception as e:
            logger.error("Error collecting social data", error=str(e))
            return {'error': str(e), 'posts_count': 0, 'comments_count': 0, 'likes_count': 0}
    
    # Helper methods for data analysis
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate trend direction using linear regression"""
        if len(values) < 2:
            return 'stable'
        
        x = np.arange(len(values))
        try:
            slope, _, _, p_value, _ = stats.linregress(x, values)
            
            if p_value > 0.05:  # Not statistically significant
                return 'stable'
            elif slope > 0.1:
                return 'improving'
            elif slope < -0.1:
                return 'declining'
            else:
                return 'stable'
        except Exception:
            return 'stable'
    
    def _calculate_daily_averages(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate daily mood averages"""
        if df.empty:
            return {}
        
        df['date'] = df['timestamp'].dt.date
        daily_avg = df.groupby('date')['mood_score'].mean()
        return {str(date): float(score) for date, score in daily_avg.items()}
    
    def _analyze_activity_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze activity patterns from mood data"""
        if df.empty or 'activities' not in df.columns:
            return {}
        
        # This is a simplified analysis - would need more complex logic for real activities
        activity_counts = {}
        for activities in df['activities'].dropna():
            if isinstance(activities, list):
                for activity in activities:
                    activity_counts[activity] = activity_counts.get(activity, 0) + 1
        
        return {
            'most_common_activities': sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            'total_unique_activities': len(activity_counts)
        }
    
    def _calculate_mood_improvement(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate mood improvement from journal entries"""
        if df.empty or 'mood_before' not in df.columns or 'mood_after' not in df.columns:
            return {'avg_improvement': 0.0, 'entries_with_improvement': 0}
        
        mood_diffs = df['mood_after'] - df['mood_before']
        mood_diffs = mood_diffs.dropna()
        
        return {
            'avg_improvement': float(mood_diffs.mean()) if not mood_diffs.empty else 0.0,
            'entries_with_improvement': int((mood_diffs > 0).sum()),
            'entries_with_decline': int((mood_diffs < 0).sum())
        }
    
    def _analyze_journal_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sentiment in journal entries"""
        # Simplified sentiment analysis - would use proper NLP in production
        if df.empty or 'content' not in df.columns:
            return {'avg_sentiment': 0.0, 'sentiment_trend': 'neutral'}
        
        # Placeholder sentiment analysis
        positive_words = ['happy', 'good', 'great', 'excellent', 'wonderful', 'amazing']
        negative_words = ['sad', 'bad', 'terrible', 'awful', 'horrible', 'depressed']
        
        sentiments = []
        for content in df['content'].fillna(''):
            content_lower = content.lower()
            positive_count = sum(1 for word in positive_words if word in content_lower)
            negative_count = sum(1 for word in negative_words if word in content_lower)
            sentiment = positive_count - negative_count
            sentiments.append(sentiment)
        
        avg_sentiment = np.mean(sentiments) if sentiments else 0.0
        
        return {
            'avg_sentiment': float(avg_sentiment),
            'sentiment_trend': 'positive' if avg_sentiment > 0.5 else 'negative' if avg_sentiment < -0.5 else 'neutral'
        }
    
    def _extract_journal_topics(self, df: pd.DataFrame) -> List[str]:
        """Extract main topics from journal entries"""
        # Simplified topic extraction - would use proper NLP/topic modeling
        if df.empty or 'content' not in df.columns:
            return []
        
        # Common mental health topics
        topics = {
            'anxiety': ['anxiety', 'anxious', 'worried', 'stress'],
            'depression': ['depression', 'depressed', 'sad', 'down'],
            'relationships': ['relationship', 'friend', 'family', 'partner'],
            'work': ['work', 'job', 'career', 'office'],
            'sleep': ['sleep', 'tired', 'insomnia', 'rest'],
            'health': ['health', 'exercise', 'diet', 'physical']
        }
        
        topic_counts = {}
        for content in df['content'].fillna(''):
            content_lower = content.lower()
            for topic, keywords in topics.items():
                count = sum(1 for keyword in keywords if keyword in content_lower)
                topic_counts[topic] = topic_counts.get(topic, 0) + count
        
        # Return top 3 topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, count in sorted_topics[:3] if count > 0]
    
    def _analyze_writing_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze journal writing frequency patterns"""
        if df.empty:
            return {'avg_per_week': 0.0, 'consistency': 'low'}
        
        df['date'] = pd.to_datetime(df['created_at']).dt.date
        df['week'] = pd.to_datetime(df['created_at']).dt.isocalendar().week
        
        weekly_counts = df.groupby('week').size()
        avg_per_week = weekly_counts.mean() if not weekly_counts.empty else 0.0
        
        # Determine consistency
        if avg_per_week >= 5:
            consistency = 'high'
        elif avg_per_week >= 2:
            consistency = 'medium'
        else:
            consistency = 'low'
        
        return {
            'avg_per_week': float(avg_per_week),
            'consistency': consistency,
            'total_weeks': len(weekly_counts)
        }
    
    def _analyze_communication_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze communication frequency patterns"""
        if df.empty:
            return {}
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.day_name()
        
        return {
            'messages_per_hour': df['hour'].value_counts().to_dict(),
            'messages_per_day': df['day_of_week'].value_counts().to_dict(),
            'avg_messages_per_day': len(df) / df['timestamp'].dt.date.nunique() if not df.empty else 0.0
        }
    
    def _analyze_message_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze sentiment in messages"""
        # Simplified sentiment analysis
        if df.empty:
            return {'avg_sentiment': 0.0}
        
        # Basic sentiment scoring
        positive_words = ['thanks', 'good', 'great', 'happy', 'love', 'excellent']
        negative_words = ['bad', 'sad', 'angry', 'hate', 'terrible', 'awful']
        
        sentiments = []
        for content in df['content'].fillna(''):
            content_lower = content.lower()
            positive_count = sum(1 for word in positive_words if word in content_lower)
            negative_count = sum(1 for word in negative_words if word in content_lower)
            sentiment = positive_count - negative_count
            sentiments.append(sentiment)
        
        return {
            'avg_sentiment': float(np.mean(sentiments)) if sentiments else 0.0
        }
    
    def _calculate_attendance_rate(self, df: pd.DataFrame) -> float:
        """Calculate appointment attendance rate"""
        if df.empty:
            return 0.0
        
        total_scheduled = len(df[df['status'].isin(['completed', 'cancelled'])])
        completed = len(df[df['status'] == 'completed'])
        
        return float(completed / total_scheduled) if total_scheduled > 0 else 0.0
    
    def _analyze_appointment_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze appointment frequency patterns"""
        if df.empty:
            return {}
        
        df['appointment_date'] = pd.to_datetime(df['appointment_date'])
        df['week'] = df['appointment_date'].dt.isocalendar().week
        
        weekly_counts = df.groupby('week').size()
        
        return {
            'avg_per_week': float(weekly_counts.mean()) if not weekly_counts.empty else 0.0,
            'total_weeks_with_appointments': len(weekly_counts)
        }
    
    def _analyze_feature_usage(self, df: pd.DataFrame) -> List[str]:
        """Analyze most used features"""
        if df.empty or 'features_used' not in df.columns:
            return []
        
        feature_counts = {}
        for features in df['features_used'].dropna():
            if isinstance(features, list):
                for feature in features:
                    feature_counts[feature] = feature_counts.get(feature, 0) + 1
        
        sorted_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)
        return [feature for feature, count in sorted_features[:5]]
    
    def _calculate_engagement_trend(self, df: pd.DataFrame) -> str:
        """Calculate user engagement trend"""
        if df.empty or 'sessions_count' not in df.columns:
            return 'stable'
        
        sessions = df['sessions_count'].values
        return self._calculate_trend(sessions)
    
    def _calculate_social_engagement(self, posts, comments, likes) -> Dict[str, Any]:
        """Calculate social engagement metrics"""
        total_posts = len(posts)
        total_comments = len(comments)
        total_likes = len(likes)
        
        return {
            'total_interactions': total_posts + total_comments + total_likes,
            'posts_ratio': total_posts / (total_posts + total_comments + total_likes) if (total_posts + total_comments + total_likes) > 0 else 0.0,
            'engagement_level': 'high' if (total_posts + total_comments + total_likes) > 20 else 'medium' if (total_posts + total_comments + total_likes) > 5 else 'low'
        }
    
    def _update_performance_metrics(self, start_time: float, data_sources_count: int, errors: List[str]):
        """Update performance tracking metrics"""
        collection_time = time.time() - start_time
        
        self.collection_stats['total_collections'] += 1
        self.collection_stats['avg_collection_time'] = (
            (self.collection_stats['avg_collection_time'] * (self.collection_stats['total_collections'] - 1) + collection_time) 
            / self.collection_stats['total_collections']
        )
        
        if errors:
            self.collection_stats['error_rate'] = (
                self.collection_stats['error_rate'] * (self.collection_stats['total_collections'] - 1) + 1
            ) / self.collection_stats['total_collections']
        
        logger.info("Performance metrics updated", 
                   collection_time=collection_time,
                   data_sources=data_sources_count,
                   errors_count=len(errors))


# Create singleton instance
data_collector = DataCollectionService()

# Export singleton
__all__ = ['data_collector', 'DataCollectionService', 'UserDataSnapshot', 'DataCollectionMetrics']

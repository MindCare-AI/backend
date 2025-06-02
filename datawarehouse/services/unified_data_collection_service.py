# datawarehouse/services/unified_data_collection_service.py
"""
Unified Data Collection Service that integrates specialized collection services
"""
from typing import Dict, Any, Optional
from datetime import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging
from dataclasses import dataclass, asdict
import time

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class UnifiedDataSnapshot:
    """Unified data snapshot combining specialized services and legacy data"""
    user_id: int
    collection_date: datetime
    period_days: int
    
    # Specialized service data
    user_behavior_analytics: Optional[Dict[str, Any]] = None
    mood_journal_analytics: Optional[Dict[str, Any]] = None
    therapist_session_analytics: Optional[Dict[str, Any]] = None
    feeds_analytics: Optional[Dict[str, Any]] = None
    
    # Legacy data for backwards compatibility
    legacy_mood_data: Optional[Dict[str, Any]] = None
    legacy_journal_data: Optional[Dict[str, Any]] = None
    legacy_messaging_data: Optional[Dict[str, Any]] = None
    legacy_appointment_data: Optional[Dict[str, Any]] = None
    legacy_notification_data: Optional[Dict[str, Any]] = None
    legacy_analytics_data: Optional[Dict[str, Any]] = None
    legacy_social_data: Optional[Dict[str, Any]] = None
    
    # Metadata
    collection_metadata: Optional[Dict[str, Any]] = None


class UnifiedDataCollectionService:
    """
    Unified service that orchestrates data collection from both specialized services
    and legacy collection methods
    """
    
    def __init__(self):
        self.specialized_services = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all available specialized collection services"""
        try:
            # Initialize therapist session service
            try:
                from .therapist_session_notes_service import TherapistSessionNotesCollectionService
                self.specialized_services['therapist'] = TherapistSessionNotesCollectionService()
                logger.info("TherapistSessionNotesCollectionService initialized")
            except ImportError as e:
                logger.warning(f"TherapistSessionNotesCollectionService not available: {e}")
            
            # Initialize feeds service
            try:
                from .feeds_service import FeedsCollectionService
                self.specialized_services['feeds'] = FeedsCollectionService()
                logger.info("FeedsCollectionService initialized")
            except ImportError as e:
                logger.warning(f"FeedsCollectionService not available: {e}")
            
            # Initialize mood journal service if it exists
            try:
                from .mood_collection_service import MoodCollectionService
                self.specialized_services['mood_journal'] = MoodCollectionService()
                logger.info("MoodCollectionService initialized")
            except ImportError as e:
                logger.warning(f"MoodCollectionService not available: {e}")
            
            # Initialize user behavior service if it exists - placeholder for future implementation
            # try:
            #     from .user_behavior_service import UserBehaviorCollectionService
            #     self.specialized_services['user_behavior'] = UserBehaviorCollectionService()
            #     logger.info("UserBehaviorCollectionService initialized")
            # except ImportError as e:
            #     logger.warning(f"UserBehaviorCollectionService not available: {e}")
                
        except Exception as e:
            logger.error(f"Error initializing specialized services: {str(e)}")
    
    def collect_unified_data(self, user_id: int, days: int = 30) -> UnifiedDataSnapshot:
        """
        Collect data from all available specialized services and create unified snapshot
        """
        start_time = time.time()
        
        try:
            user = User.objects.get(id=user_id)
            
            # Collect from specialized services
            specialized_data = {}
            
            if 'therapist' in self.specialized_services:
                try:
                    snapshot = self.specialized_services['therapist'].collect_therapist_session_data(user, days)
                    specialized_data['therapist_session_analytics'] = asdict(snapshot) if snapshot else {}
                except Exception as e:
                    logger.error(f"Error collecting therapist data: {str(e)}")
                    specialized_data['therapist_session_analytics'] = {}
            
            if 'feeds' in self.specialized_services:
                try:
                    snapshot = self.specialized_services['feeds'].collect_feeds_data(user, days)
                    specialized_data['feeds_analytics'] = asdict(snapshot) if snapshot else {}
                except Exception as e:
                    logger.error(f"Error collecting feeds data: {str(e)}")
                    specialized_data['feeds_analytics'] = {}
            
            if 'mood_journal' in self.specialized_services:
                try:
                    snapshot = self.specialized_services['mood_journal'].collect_mood_journal_data(user, days)
                    specialized_data['mood_journal_analytics'] = asdict(snapshot) if snapshot else {}
                except Exception as e:
                    logger.error(f"Error collecting mood journal data: {str(e)}")
                    specialized_data['mood_journal_analytics'] = {}
            
            if 'user_behavior' in self.specialized_services:
                try:
                    snapshot = self.specialized_services['user_behavior'].collect_user_behavior_data(user, days)
                    specialized_data['user_behavior_analytics'] = asdict(snapshot) if snapshot else {}
                except Exception as e:
                    logger.error(f"Error collecting user behavior data: {str(e)}")
                    specialized_data['user_behavior_analytics'] = {}
            
            # Create unified snapshot
            unified_snapshot = UnifiedDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                user_behavior_analytics=specialized_data.get('user_behavior_analytics'),
                mood_journal_analytics=specialized_data.get('mood_journal_analytics'),
                therapist_session_analytics=specialized_data.get('therapist_session_analytics'),
                feeds_analytics=specialized_data.get('feeds_analytics'),
                collection_metadata={
                    'collection_time': time.time() - start_time,
                    'specialized_services_used': list(self.specialized_services.keys()),
                    'data_sources_collected': list(specialized_data.keys()),
                    'version': '1.0'
                }
            )
            
            logger.info(f"Unified data collection completed for user {user_id} in {time.time() - start_time:.2f}s")
            return unified_snapshot
            
        except Exception as e:
            logger.error(f"Error in unified data collection: {str(e)}")
            # Return empty snapshot with error info
            return UnifiedDataSnapshot(
                user_id=user_id,
                collection_date=timezone.now(),
                period_days=days,
                collection_metadata={
                    'collection_time': time.time() - start_time,
                    'error': str(e),
                    'version': '1.0'
                }
            )
    
    def collect_comprehensive_user_data(self, user_id: int, date_range: int = 30) -> Dict[str, Any]:
        """
        Enhanced data collection for AI analysis with comprehensive aggregation
        """
        try:
            from django.utils import timezone
            import time
            
            start_time = time.time()
            user = User.objects.get(id=user_id)
            
            # Collect unified snapshot first
            unified_snapshot = self.collect_unified_data(user_id, date_range)
            
            # Generate AI-ready aggregated data
            ai_ready_data = {
                'mood_analytics': self._aggregate_mood_data(user, date_range, unified_snapshot),
                'journal_analytics': self._aggregate_journal_data(user, date_range, unified_snapshot),
                'communication_analytics': self._aggregate_communication_data(user, date_range, unified_snapshot),
                'therapy_session_analytics': self._aggregate_therapy_data(user, date_range, unified_snapshot),
                'behavioral_analytics': self._aggregate_behavioral_data(user, date_range, unified_snapshot),
                'social_analytics': self._aggregate_social_data(user, date_range, unified_snapshot),
                'processed_insights': self._generate_cross_domain_insights(user, date_range, unified_snapshot)
            }
            
            # Calculate data quality and completeness
            quality_metrics = self._calculate_data_quality(ai_ready_data, unified_snapshot)
            
            # Enhanced metadata
            processing_metadata = {
                'collection_time_seconds': time.time() - start_time,
                'data_sources_used': list(self.specialized_services.keys()),
                'processing_version': '2.0_ai_ready',
                'quality_score': quality_metrics['overall_quality'],
                'completeness_score': quality_metrics['completeness'],
                'readiness_flags': quality_metrics['readiness_flags'],
                'collection_timestamp': timezone.now().isoformat(),
                'user_id': user_id,
                'period_days': date_range
            }
            
            result = {
                **ai_ready_data,
                'quality_metrics': quality_metrics,
                'processing_metadata': processing_metadata,
                'raw_unified_snapshot': unified_snapshot  # Keep for backwards compatibility
            }
            
            logger.info(f"Comprehensive data collection completed for user {user_id} in {time.time() - start_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive data collection: {str(e)}")
            return self._create_empty_comprehensive_dataset(user_id, date_range, str(e))
    
    def get_ai_ready_dataset(self, user_id: int, date_range: int = 30, 
                           analysis_types: list = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get or create AI-ready dataset with caching support
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            from datawarehouse.models import AIAnalysisDataset
            
            # Check for existing valid cached dataset
            if use_cache:
                cached_dataset = AIAnalysisDataset.objects.filter(
                    user_id=user_id,
                    period_days=date_range,
                    is_active=True,
                    expires_at__gt=timezone.now()
                ).order_by('-collection_date').first()
                
                if cached_dataset:
                    logger.info(f"Using cached AI dataset for user {user_id}")
                    return self._format_cached_dataset_for_ai(cached_dataset)
            
            # Generate new dataset
            comprehensive_data = self.collect_comprehensive_user_data(user_id, date_range)
            
            # Cache the dataset
            self._cache_ai_dataset(user_id, date_range, comprehensive_data)
            
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"Error getting AI-ready dataset: {str(e)}")
            return self._create_empty_comprehensive_dataset(user_id, date_range, str(e))
    
    def _aggregate_mood_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate mood data for AI analysis"""
        try:
            from mood.models import MoodLog
            from django.utils import timezone
            from datetime import timedelta
            import statistics
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=date_range)
            
            mood_logs = MoodLog.objects.filter(
                user=user,
                timestamp__range=[start_date, end_date]
            ).order_by('timestamp')
            
            if not mood_logs:
                return {'status': 'no_data', 'entries_count': 0}
            
            mood_scores = [log.mood_score for log in mood_logs]
            daily_moods = {}
            
            for log in mood_logs:
                day = log.timestamp.date()
                if day not in daily_moods:
                    daily_moods[day] = []
                daily_moods[day].append(log.mood_score)
            
            # Calculate aggregated metrics
            aggregated_data = {
                'total_entries': len(mood_logs),
                'date_range': date_range,
                'average_mood': statistics.mean(mood_scores) if mood_scores else 0,
                'median_mood': statistics.median(mood_scores) if mood_scores else 0,
                'mood_volatility': statistics.stdev(mood_scores) if len(mood_scores) > 1 else 0,
                'min_mood': min(mood_scores) if mood_scores else 0,
                'max_mood': max(mood_scores) if mood_scores else 0,
                'mood_range': max(mood_scores) - min(mood_scores) if mood_scores else 0,
                'daily_averages': {str(day): statistics.mean(scores) for day, scores in daily_moods.items()},
                'trend_analysis': self._calculate_mood_trend(daily_moods),
                'patterns': self._analyze_mood_patterns(mood_logs),
                'consistency_score': self._calculate_mood_consistency(daily_moods),
                'quality_indicators': {
                    'data_density': len(mood_logs) / date_range,
                    'temporal_coverage': len(daily_moods) / date_range,
                    'completeness': min(1.0, len(mood_logs) / (date_range * 0.5))  # Expect at least 0.5 entries per day for full score
                }
            }
            
            # Add specialized service data if available
            if unified_snapshot.mood_journal_analytics:
                aggregated_data['specialized_analytics'] = unified_snapshot.mood_journal_analytics
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating mood data: {str(e)}")
            return {'status': 'error', 'error': str(e), 'entries_count': 0}
    
    def _aggregate_journal_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate journal data for AI analysis"""
        try:
            from journal.models import JournalEntry
            from django.utils import timezone
            from datetime import timedelta
            import statistics
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=date_range)
            
            journal_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__range=[start_date, end_date]
            ).order_by('timestamp')
            
            if not journal_entries:
                return {'status': 'no_data', 'entries_count': 0}
            
            # Analyze text content
            entries_data = []
            total_words = 0
            word_counts = []
            
            for entry in journal_entries:
                content = entry.content or ""
                word_count = len(content.split())
                word_counts.append(word_count)
                total_words += word_count
                
                entries_data.append({
                    'date': entry.timestamp.date().isoformat(),
                    'word_count': word_count,
                    'content_length': len(content),
                    'has_content': bool(content.strip())
                })
            
            aggregated_data = {
                'total_entries': len(journal_entries),
                'date_range': date_range,
                'total_words': total_words,
                'average_words_per_entry': statistics.mean(word_counts) if word_counts else 0,
                'median_words_per_entry': statistics.median(word_counts) if word_counts else 0,
                'writing_consistency': self._calculate_writing_consistency(journal_entries),
                'temporal_patterns': self._analyze_writing_patterns(journal_entries),
                'content_diversity': self._analyze_content_diversity(journal_entries),
                'entries_metadata': entries_data,
                'quality_indicators': {
                    'data_density': len(journal_entries) / date_range,
                    'content_richness': total_words / max(len(journal_entries), 1),
                    'temporal_coverage': len(set(e.timestamp.date() for e in journal_entries)) / date_range,
                    'completeness': min(1.0, len(journal_entries) / (date_range * 0.3))  # Expect at least 0.3 entries per day
                }
            }
            
            # Add specialized service data if available
            if unified_snapshot.mood_journal_analytics:
                aggregated_data['specialized_analytics'] = unified_snapshot.mood_journal_analytics
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating journal data: {str(e)}")
            return {'status': 'error', 'error': str(e), 'entries_count': 0}
    
    def _aggregate_communication_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate communication data for AI analysis"""
        try:
            # This would integrate with messaging and communication systems
            # For now, return basic structure with specialized service data
            aggregated_data = {
                'status': 'partial_implementation',
                'date_range': date_range,
                'specialized_analytics': unified_snapshot.feeds_analytics if unified_snapshot.feeds_analytics else {},
                'quality_indicators': {
                    'data_availability': bool(unified_snapshot.feeds_analytics),
                    'completeness': 0.5 if unified_snapshot.feeds_analytics else 0.0
                }
            }
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating communication data: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _aggregate_therapy_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate therapy session data for AI analysis"""
        try:
            aggregated_data = {
                'status': 'from_specialized_service',
                'date_range': date_range,
                'specialized_analytics': unified_snapshot.therapist_session_analytics if unified_snapshot.therapist_session_analytics else {},
                'quality_indicators': {
                    'data_availability': bool(unified_snapshot.therapist_session_analytics),
                    'completeness': 0.8 if unified_snapshot.therapist_session_analytics else 0.0
                }
            }
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating therapy data: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _aggregate_behavioral_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate behavioral data for AI analysis"""
        try:
            aggregated_data = {
                'status': 'from_specialized_service',
                'date_range': date_range,
                'specialized_analytics': unified_snapshot.user_behavior_analytics if unified_snapshot.user_behavior_analytics else {},
                'quality_indicators': {
                    'data_availability': bool(unified_snapshot.user_behavior_analytics),
                    'completeness': 0.7 if unified_snapshot.user_behavior_analytics else 0.0
                }
            }
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating behavioral data: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _aggregate_social_data(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Aggregate social engagement data for AI analysis"""
        try:
            aggregated_data = {
                'status': 'from_specialized_service',
                'date_range': date_range,
                'specialized_analytics': unified_snapshot.feeds_analytics if unified_snapshot.feeds_analytics else {},
                'quality_indicators': {
                    'data_availability': bool(unified_snapshot.feeds_analytics),
                    'completeness': 0.6 if unified_snapshot.feeds_analytics else 0.0
                }
            }
            
            return aggregated_data
            
        except Exception as e:
            logger.error(f"Error aggregating social data: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _generate_cross_domain_insights(self, user, date_range: int, unified_snapshot) -> Dict[str, Any]:
        """Generate cross-domain insights from multiple data sources"""
        try:
            insights = {
                'cross_correlations': {},
                'pattern_detection': {},
                'data_synthesis': {},
                'quality_score': 0.0
            }
            
            # This would contain sophisticated cross-domain analysis
            # For now, return basic structure
            insights['metadata'] = {
                'analysis_version': '1.0',
                'generated_at': timezone.now().isoformat(),
                'data_sources_analyzed': len([s for s in [
                    unified_snapshot.mood_journal_analytics,
                    unified_snapshot.therapist_session_analytics,
                    unified_snapshot.user_behavior_analytics,
                    unified_snapshot.feeds_analytics
                ] if s])
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating cross-domain insights: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _calculate_data_quality(self, ai_ready_data: Dict[str, Any], unified_snapshot) -> Dict[str, Any]:
        """Calculate comprehensive data quality metrics"""
        try:
            quality_scores = {}
            readiness_flags = {}
            
            # Calculate quality for each domain
            for domain in ['mood_analytics', 'journal_analytics', 'communication_analytics', 
                          'therapy_session_analytics', 'behavioral_analytics', 'social_analytics']:
                domain_data = ai_ready_data.get(domain, {})
                quality_indicators = domain_data.get('quality_indicators', {})
                
                quality_scores[domain] = quality_indicators.get('completeness', 0.0)
                readiness_flags[f"ready_for_{domain.replace('_analytics', '_analysis')}"] = quality_scores[domain] >= 0.3
            
            overall_quality = sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0.0
            overall_completeness = min(1.0, overall_quality * 1.2) # Slight boost for having multiple sources
            
            return {
                'overall_quality': overall_quality,
                'completeness': overall_completeness,
                'domain_scores': quality_scores,
                'readiness_flags': readiness_flags,
                'analysis_recommendation': 'suitable' if overall_quality >= 0.5 else 'limited' if overall_quality >= 0.2 else 'insufficient'
            }
            
        except Exception as e:
            logger.error(f"Error calculating data quality: {str(e)}")
            return {'overall_quality': 0.0, 'completeness': 0.0, 'error': str(e)}
    
    def _cache_ai_dataset(self, user_id: int, period_days: int, comprehensive_data: Dict[str, Any]):
        """Cache AI-ready dataset in database"""
        try:
            from django.utils import timezone
            from datetime import timedelta
            from datawarehouse.models import AIAnalysisDataset
            
            # Calculate expiration (datasets expire after 6 hours for real-time accuracy)
            expires_at = timezone.now() + timedelta(hours=6)
            
            quality_metrics = comprehensive_data.get('quality_metrics', {})
            processing_metadata = comprehensive_data.get('processing_metadata', {})
            
            dataset = AIAnalysisDataset.objects.create(
                user_id=user_id,
                period_days=period_days,
                mood_summary=comprehensive_data.get('mood_analytics', {}),
                journal_insights=comprehensive_data.get('journal_analytics', {}),
                behavioral_patterns=comprehensive_data.get('behavioral_analytics', {}),
                communication_metrics=comprehensive_data.get('communication_analytics', {}),
                therapy_session_data=comprehensive_data.get('therapy_session_analytics', {}),
                social_engagement_data=comprehensive_data.get('social_analytics', {}),
                risk_indicators=comprehensive_data.get('processed_insights', {}),
                data_completeness_score=quality_metrics.get('completeness', 0.0),
                data_quality_indicators=quality_metrics,
                confidence_score=quality_metrics.get('overall_quality', 0.0),
                processing_version='2.0',
                data_sources_used=processing_metadata.get('data_sources_used', []),
                processing_duration_seconds=processing_metadata.get('collection_time_seconds', 0),
                ready_for_mood_analysis=quality_metrics.get('readiness_flags', {}).get('ready_for_mood_analysis', False),
                ready_for_journal_analysis=quality_metrics.get('readiness_flags', {}).get('ready_for_journal_analysis', False),
                ready_for_behavior_analysis=quality_metrics.get('readiness_flags', {}).get('ready_for_behavioral_analysis', False),
                ready_for_communication_analysis=quality_metrics.get('readiness_flags', {}).get('ready_for_communication_analysis', False),
                ready_for_therapy_analysis=quality_metrics.get('readiness_flags', {}).get('ready_for_therapy_session_analysis', False),
                expires_at=expires_at
            )
            
            logger.info(f"Cached AI dataset for user {user_id}, expires at {expires_at}")
            return dataset
            
        except Exception as e:
            logger.error(f"Error caching AI dataset: {str(e)}")
            return None
    
    def _format_cached_dataset_for_ai(self, cached_dataset) -> Dict[str, Any]:
        """Format cached dataset for AI consumption"""
        return {
            'mood_analytics': cached_dataset.mood_summary,
            'journal_analytics': cached_dataset.journal_insights,
            'communication_analytics': cached_dataset.communication_metrics,
            'therapy_session_analytics': cached_dataset.therapy_session_data,
            'behavioral_analytics': cached_dataset.behavioral_patterns,
            'social_analytics': cached_dataset.social_engagement_data,
            'processed_insights': cached_dataset.risk_indicators,
            'quality_metrics': cached_dataset.data_quality_indicators,
            'processing_metadata': {
                'collection_time_seconds': cached_dataset.processing_duration_seconds,
                'data_sources_used': cached_dataset.data_sources_used,
                'processing_version': cached_dataset.processing_version,
                'quality_score': cached_dataset.confidence_score,
                'completeness_score': cached_dataset.data_completeness_score,
                'collection_timestamp': cached_dataset.collection_date.isoformat(),
                'cached': True,
                'cache_expires_at': cached_dataset.expires_at.isoformat()
            }
        }
    
    def _create_empty_comprehensive_dataset(self, user_id: int, date_range: int, error: str = None) -> Dict[str, Any]:
        """Create empty dataset structure for error cases"""
        return {
            'mood_analytics': {'status': 'error', 'error': error},
            'journal_analytics': {'status': 'error', 'error': error},
            'communication_analytics': {'status': 'error', 'error': error},
            'therapy_session_analytics': {'status': 'error', 'error': error},
            'behavioral_analytics': {'status': 'error', 'error': error},
            'social_analytics': {'status': 'error', 'error': error},
            'processed_insights': {'status': 'error', 'error': error},
            'quality_metrics': {'overall_quality': 0.0, 'completeness': 0.0, 'error': error},
            'processing_metadata': {
                'collection_time_seconds': 0,
                'data_sources_used': [],
                'processing_version': '2.0_error',
                'error': error,
                'user_id': user_id,
                'period_days': date_range
            }
        }
    
    # Helper methods for data analysis
    def _calculate_mood_trend(self, daily_moods: Dict) -> Dict[str, Any]:
        """Calculate mood trend over time"""
        if len(daily_moods) < 2:
            return {'trend': 'insufficient_data', 'strength': 0.0}
        
        # Simple linear trend calculation
        import statistics
        sorted_days = sorted(daily_moods.keys())
        daily_averages = [statistics.mean(daily_moods[day]) for day in sorted_days]
        
        # Calculate slope
        n = len(daily_averages)
        x_mean = n / 2
        y_mean = statistics.mean(daily_averages)
        
        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_averages))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # Determine trend
        if slope > 0.1:
            trend = 'improving'
        elif slope < -0.1:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'strength': abs(slope),
            'slope': slope,
            'daily_averages': daily_averages
        }
    
    def _analyze_mood_patterns(self, mood_logs) -> Dict[str, Any]:
        """Analyze patterns in mood data"""
        patterns = {
            'weekly_patterns': {},
            'daily_patterns': {},
            'temporal_insights': {}
        }
        
        # Group by day of week
        from collections import defaultdict
        weekly_moods = defaultdict(list)
        hourly_moods = defaultdict(list)
        
        for log in mood_logs:
            day_of_week = log.timestamp.strftime('%A')
            hour = log.timestamp.hour
            
            weekly_moods[day_of_week].append(log.mood_score)
            hourly_moods[hour].append(log.mood_score)
        
        # Calculate averages
        import statistics
        patterns['weekly_patterns'] = {
            day: statistics.mean(scores) for day, scores in weekly_moods.items()
        }
        patterns['daily_patterns'] = {
            hour: statistics.mean(scores) for hour, scores in hourly_moods.items()
        }
        
        return patterns
    
    def _calculate_mood_consistency(self, daily_moods: Dict) -> float:
        """Calculate mood consistency score"""
        if len(daily_moods) < 3:
            return 0.0
        
        import statistics
        daily_averages = [statistics.mean(scores) for scores in daily_moods.values()]
        variance = statistics.variance(daily_averages) if len(daily_averages) > 1 else 0
        
        # Convert variance to consistency score (0-1, higher is more consistent)
        consistency = max(0.0, 1.0 - (variance / 25.0))  # Assuming mood scale 1-10
        return min(1.0, consistency)
    
    def _calculate_writing_consistency(self, journal_entries) -> Dict[str, Any]:
        """Calculate writing consistency metrics"""
        if len(journal_entries) < 3:
            return {'score': 0.0, 'pattern': 'insufficient_data'}
        
        # Analyze writing frequency
        from collections import defaultdict
        daily_counts = defaultdict(int)
        
        for entry in journal_entries:
            day = entry.timestamp.date()
            daily_counts[day] += 1
        
        # Calculate consistency
        import statistics
        daily_entries = list(daily_counts.values())
        avg_entries = statistics.mean(daily_entries)
        std_entries = statistics.stdev(daily_entries) if len(daily_entries) > 1 else 0
        
        # Consistency score (lower standard deviation = higher consistency)
        consistency = max(0.0, 1.0 - (std_entries / (avg_entries + 1)))
        
        return {
            'score': consistency,
            'average_entries_per_day': avg_entries,
            'variability': std_entries,
            'pattern': 'consistent' if consistency > 0.7 else 'variable' if consistency > 0.3 else 'irregular'
        }
    
    def _analyze_writing_patterns(self, journal_entries) -> Dict[str, Any]:
        """Analyze temporal patterns in journaling"""
        patterns = {
            'preferred_times': {},
            'weekly_patterns': {},
            'frequency_analysis': {}
        }
        
        from collections import defaultdict
        hourly_entries = defaultdict(int)
        weekly_entries = defaultdict(int)
        
        for entry in journal_entries:
            hour = entry.timestamp.hour
            day_of_week = entry.timestamp.strftime('%A')
            
            hourly_entries[hour] += 1
            weekly_entries[day_of_week] += 1
        
        patterns['preferred_times'] = dict(hourly_entries)
        patterns['weekly_patterns'] = dict(weekly_entries)
        patterns['frequency_analysis'] = {
            'total_entries': len(journal_entries),
            'active_hours': len(hourly_entries),
            'active_days': len(weekly_entries)
        }
        
        return patterns
    
    def _analyze_content_diversity(self, journal_entries) -> Dict[str, Any]:
        """Analyze diversity in journal content"""
        if not journal_entries:
            return {'score': 0.0, 'analysis': 'no_content'}
        
        # Basic content analysis
        word_sets = []
        total_words = 0
        
        for entry in journal_entries:
            content = entry.content or ""
            words = set(content.lower().split())
            word_sets.append(words)
            total_words += len(words)
        
        # Calculate diversity
        all_words = set()
        for word_set in word_sets:
            all_words.update(word_set)
        
        unique_words = len(all_words)
        avg_words_per_entry = total_words / max(len(journal_entries), 1)
        
        # Diversity score
        diversity = min(1.0, unique_words / max(total_words, 1) * 10)  # Normalize
        
        return {
            'score': diversity,
            'unique_words': unique_words,
            'total_words': total_words,
            'average_words_per_entry': avg_words_per_entry,
            'analysis': 'diverse' if diversity > 0.7 else 'moderate' if diversity > 0.4 else 'repetitive'
        }

# Create singleton instance
unified_data_collector = UnifiedDataCollectionService()

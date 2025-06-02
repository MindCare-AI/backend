# datawarehouse/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    DataCollectionRun, 
    UserDataSnapshot, 
    MoodTrendAnalysis,
    JournalInsightCache,
    CommunicationMetrics,
    FeatureUsageMetrics,
    PredictiveModel,
    DataQualityReport
)

User = get_user_model()


class DataCollectionRunSerializer(serializers.ModelSerializer):
    """Serializer for data collection run tracking"""
    duration_minutes = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = DataCollectionRun
        fields = [
            'id', 'run_type', 'status', 'started_at', 'completed_at',
            'records_processed', 'errors_count', 'metadata', 
            'duration_minutes', 'success_rate'
        ]
        read_only_fields = ['id', 'started_at']
    
    def get_duration_minutes(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            return round(delta.total_seconds() / 60, 2)
        return None
    
    def get_success_rate(self, obj):
        if obj.records_processed > 0:
            success_rate = ((obj.records_processed - obj.errors_count) / obj.records_processed) * 100
            return round(success_rate, 2)
        return 0.0


class UserDataSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for user data snapshots"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = UserDataSnapshot
        fields = [
            'id', 'user', 'user_email', 'user_full_name', 'snapshot_date',
            # Mood analytics
            'mood_entries_count', 'avg_mood_score', 'mood_volatility', 
            'dominant_mood', 'mood_trend',
            # Journal analytics
            'journal_entries_count', 'avg_journal_length', 'total_words_written',
            'avg_sentiment_score', 'writing_consistency_score', 'journal_topics',
            # Communication analytics
            'messages_sent', 'messages_received', 'avg_response_time_minutes',
            'communication_sentiment',
            # Activity analytics
            'app_sessions_count', 'total_session_duration_minutes', 'features_used',
            # Social analytics
            'posts_created', 'comments_made', 'likes_given', 'likes_received',
            'social_engagement_score',
            # Risk indicators
            'crisis_indicators_count', 'risk_score', 'needs_attention',
            # Metadata
            'data_completeness_score', 'data_quality_score', 'last_updated',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


class MoodTrendAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for mood trend analysis"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    period_duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = MoodTrendAnalysis
        fields = [
            'id', 'user', 'user_email', 'analysis_type', 'period_start', 'period_end',
            'period_duration_days', 'trend_direction', 'trend_strength', 'volatility_score',
            'consistency_score', 'avg_mood', 'median_mood', 'min_mood', 'max_mood',
            'mood_range', 'pattern_data', 'correlation_data', 'anomalies',
            'next_period_prediction', 'prediction_confidence', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_period_duration_days(self, obj):
        delta = obj.period_end - obj.period_start
        return delta.days + 1


class JournalInsightCacheSerializer(serializers.ModelSerializer):
    """Serializer for journal insight cache"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalInsightCache
        fields = [
            'id', 'user', 'user_email', 'analysis_date', 'period_days',
            'sentiment_trends', 'emotion_distribution', 'sentiment_volatility',
            'topic_clusters', 'keyword_frequency', 'themes_evolution',
            'writing_patterns', 'linguistic_features', 'readability_scores',
            'therapeutic_progress', 'coping_strategies_mentioned', 'goals_and_intentions',
            'cache_version', 'expires_at', 'is_expired'
        ]
        read_only_fields = ['id', 'analysis_date']
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()


class CommunicationMetricsSerializer(serializers.ModelSerializer):
    """Serializer for communication metrics"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    period_duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = CommunicationMetrics
        fields = [
            'id', 'user', 'user_email', 'period_start', 'period_end', 'period_duration_days',
            'total_messages_sent', 'total_messages_received', 'avg_message_length',
            'response_rate', 'avg_response_time_hours', 'most_active_hour',
            'communication_consistency', 'therapist_conversations', 'peer_conversations',
            'support_seeking_score', 'support_giving_score', 'sentiment_distribution',
            'emotional_expression_score', 'topic_diversity', 'crisis_language_detected',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_period_duration_days(self, obj):
        delta = obj.period_end - obj.period_start
        return delta.days + 1


class FeatureUsageMetricsSerializer(serializers.ModelSerializer):
    """Serializer for feature usage metrics"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    engagement_score = serializers.SerializerMethodField()
    
    class Meta:
        model = FeatureUsageMetrics
        fields = [
            'id', 'user', 'user_email', 'date',
            # Core features
            'mood_logs_created', 'journal_entries_created', 'messages_sent',
            'appointments_scheduled',
            # Engagement
            'session_count', 'total_time_spent_minutes', 'features_used', 'engagement_score',
            # Therapeutic tools
            'breathing_exercises_completed', 'coping_strategies_accessed',
            'crisis_resources_accessed',
            # Social features
            'posts_created', 'comments_made', 'likes_given',
            # AI interactions
            'chatbot_conversations', 'ai_recommendations_viewed', 'ai_insights_acknowledged'
        ]
        read_only_fields = ['id']
    
    def get_engagement_score(self, obj):
        # Calculate a simple engagement score based on multiple factors
        score = 0
        score += min(obj.session_count * 10, 50)  # Max 50 points for sessions
        score += min(obj.total_time_spent_minutes / 5, 30)  # Max 30 points for time
        score += len(obj.features_used) * 4  # 4 points per feature used
        score += (obj.mood_logs_created + obj.journal_entries_created) * 5
        return min(score, 100)  # Cap at 100


class PredictiveModelSerializer(serializers.ModelSerializer):
    """Serializer for predictive models"""
    model_age_days = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = PredictiveModel
        fields = [
            'id', 'name', 'model_type', 'version', 'features_used', 'hyperparameters',
            'training_data_size', 'training_date', 'model_age_days',
            'accuracy', 'precision', 'recall', 'f1_score', 'auc_score',
            'performance_summary', 'is_active', 'is_production', 'model_path',
            'feature_importance', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_model_age_days(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.training_date
        return delta.days
    
    def get_performance_summary(self, obj):
        metrics = {}
        if obj.accuracy:
            metrics['accuracy'] = f"{obj.accuracy:.3f}"
        if obj.f1_score:
            metrics['f1_score'] = f"{obj.f1_score:.3f}"
        if obj.auc_score:
            metrics['auc_score'] = f"{obj.auc_score:.3f}"
        return metrics


class DataQualityReportSerializer(serializers.ModelSerializer):
    """Serializer for data quality reports"""
    total_users = serializers.SerializerMethodField()
    data_coverage_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = DataQualityReport
        fields = [
            'id', 'report_date', 'total_users', 'users_with_mood_data',
            'users_with_journal_data', 'users_with_communication_data',
            'data_completeness_score', 'data_coverage_percentage',
            'avg_data_age_hours', 'stale_records_count', 'duplicate_records_found',
            'inconsistency_issues', 'total_records_processed', 'new_records_today',
            'critical_issues', 'warnings', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_total_users(self, obj):
        # Sum of unique users across all data types
        return max(obj.users_with_mood_data, obj.users_with_journal_data, obj.users_with_communication_data)
    
    def get_data_coverage_percentage(self, obj):
        total_users = self.get_total_users(obj)
        if total_users > 0:
            covered_users = max(obj.users_with_mood_data, obj.users_with_journal_data, obj.users_with_communication_data)
            return round((covered_users / total_users) * 100, 2)
        return 0.0


class UnifiedDataSnapshotSerializer(serializers.Serializer):
    """Serializer for unified data collection snapshots"""
    user_id = serializers.IntegerField()
    collection_date = serializers.DateTimeField()
    date_range_days = serializers.IntegerField()
    
    # Data sections
    mood_data = serializers.JSONField()
    journal_data = serializers.JSONField()
    therapy_data = serializers.JSONField()
    medical_data = serializers.JSONField()
    behavioral_data = serializers.JSONField()
    messaging_data = serializers.JSONField()
    feeds_data = serializers.JSONField()
    
    # Collection metadata
    collection_metadata = serializers.JSONField()
    
    # Summary statistics
    total_data_points = serializers.IntegerField()
    data_completeness_score = serializers.FloatField()
    data_sources_used = serializers.ListField(child=serializers.CharField())


class DataCollectionSummarySerializer(serializers.Serializer):
    """Serializer for data collection summary statistics"""
    total_users = serializers.IntegerField()
    total_snapshots = serializers.IntegerField()
    total_collection_runs = serializers.IntegerField()
    avg_data_quality_score = serializers.FloatField()
    active_data_sources = serializers.IntegerField()
    last_collection_time = serializers.DateTimeField()
    
    # Data type breakdowns
    mood_entries_total = serializers.IntegerField()
    journal_entries_total = serializers.IntegerField()
    therapy_sessions_total = serializers.IntegerField()
    medical_records_total = serializers.IntegerField()
    
    # Health metrics
    system_health_score = serializers.FloatField()
    error_rate = serializers.FloatField()
    avg_processing_time = serializers.FloatField()


class UserDataDetailSerializer(serializers.Serializer):
    """Detailed serializer for individual user's collected data"""
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    data_collection_period = serializers.CharField()
    
    # Mood tracking data
    mood_summary = serializers.JSONField()
    mood_entries = serializers.ListField(child=serializers.JSONField())
    
    # Journal data
    journal_summary = serializers.JSONField()
    journal_entries = serializers.ListField(child=serializers.JSONField())
    
    # Therapy session data
    therapy_summary = serializers.JSONField()
    therapy_sessions = serializers.ListField(child=serializers.JSONField())
    
    # Medical and health data
    medical_summary = serializers.JSONField()
    health_metrics = serializers.ListField(child=serializers.JSONField())
    
    # Behavioral patterns
    behavioral_summary = serializers.JSONField()
    activity_patterns = serializers.ListField(child=serializers.JSONField())
    
    # AI insights and analysis
    ai_insights = serializers.ListField(child=serializers.JSONField())
    risk_assessments = serializers.ListField(child=serializers.JSONField())
    
    # Data quality information
    data_quality_report = serializers.JSONField()
    collection_timestamps = serializers.JSONField()

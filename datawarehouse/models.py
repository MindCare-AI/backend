# datawarehouse/models.py
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
import uuid
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


class DataCollectionRun(models.Model):
    """Tracks data collection runs for ETL monitoring"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_type = models.CharField(
        max_length=50,
        choices=[
            ("full_sync", "Full Synchronization"),
            ("incremental", "Incremental Update"),
            ("realtime", "Real-time Collection"),
            ("backfill", "Historical Backfill"),
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("partial", "Partially Completed"),
        ],
        default="running",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["run_type", "status"]),
            models.Index(fields=["-started_at"]),
        ]


class UserDataSnapshot(models.Model):
    """Daily aggregated snapshot of user data"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    snapshot_date = models.DateField()

    # Mood Analytics
    mood_entries_count = models.IntegerField(default=0)
    avg_mood_score = models.FloatField(null=True)
    mood_volatility = models.FloatField(null=True)  # Standard deviation
    dominant_mood = models.CharField(max_length=50, null=True)
    mood_trend = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
            ("volatile", "Volatile"),
        ],
        null=True,
    )

    # Journal Analytics
    journal_entries_count = models.IntegerField(default=0)
    avg_journal_length = models.FloatField(null=True)  # Average entry length
    total_words_written = models.IntegerField(default=0)
    avg_sentiment_score = models.FloatField(null=True)
    writing_consistency_score = models.FloatField(null=True)
    journal_topics = ArrayField(models.CharField(max_length=100), default=list)

    # Communication Analytics
    messages_sent = models.IntegerField(default=0)
    messages_received = models.IntegerField(default=0)
    avg_response_time_minutes = models.FloatField(null=True)
    communication_sentiment = models.FloatField(null=True)

    # Activity Analytics
    app_sessions_count = models.IntegerField(default=0)
    total_session_duration_minutes = models.IntegerField(default=0)
    features_used = ArrayField(models.CharField(max_length=50), default=list)

    # Social Analytics (feeds)
    posts_created = models.IntegerField(default=0)
    comments_made = models.IntegerField(default=0)
    likes_given = models.IntegerField(default=0)
    likes_received = models.IntegerField(default=0)
    social_engagement_score = models.FloatField(null=True)

    # Risk Indicators
    crisis_indicators_count = models.IntegerField(default=0)
    risk_score = models.FloatField(null=True)  # 0-1 scale
    needs_attention = models.BooleanField(default=False)

    # Metadata
    data_completeness_score = models.FloatField(
        default=1.0
    )  # Data completeness/quality
    data_quality_score = models.FloatField(default=1.0)  # Data completeness/quality
    last_updated = models.DateTimeField(
        null=True, blank=True
    )  # When data was last processed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "snapshot_date"]
        ordering = ["-snapshot_date"]
        indexes = [
            models.Index(fields=["user", "-snapshot_date"]),
            models.Index(fields=["snapshot_date"]),
            models.Index(fields=["risk_score"]),
            models.Index(fields=["needs_attention"]),
        ]


class MoodTrendAnalysis(models.Model):
    """Aggregated mood trend analysis over different time periods"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_type = models.CharField(
        max_length=20,
        choices=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
        ],
    )
    period_start = models.DateField()
    period_end = models.DateField()

    # Trend Metrics
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ("strongly_improving", "Strongly Improving"),
            ("improving", "Improving"),
            ("stable", "Stable"),
            ("declining", "Declining"),
            ("strongly_declining", "Strongly Declining"),
        ],
    )
    trend_strength = models.FloatField()  # How strong is the trend (0-1)
    volatility_score = models.FloatField()  # Mood volatility
    consistency_score = models.FloatField()  # How consistent are the patterns

    # Statistical Data
    avg_mood = models.FloatField()
    median_mood = models.FloatField()
    min_mood = models.FloatField()
    max_mood = models.FloatField()
    mood_range = models.FloatField()

    # Pattern Data
    pattern_data = models.JSONField(default=dict)  # Time-based patterns
    correlation_data = models.JSONField(default=dict)  # Correlations with activities
    anomalies = models.JSONField(default=list)  # Detected anomalies

    # Predictions
    next_period_prediction = models.FloatField(null=True)
    prediction_confidence = models.FloatField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "analysis_type", "period_start"]
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["user", "analysis_type", "-period_start"]),
            models.Index(fields=["trend_direction"]),
        ]


class JournalInsightCache(models.Model):
    """Cached analysis results for journal entries"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateTimeField(auto_now_add=True)
    period_days = models.IntegerField(default=30)

    # Sentiment Analysis
    sentiment_trends = models.JSONField(default=dict)  # Daily sentiment scores
    emotion_distribution = models.JSONField(default=dict)  # Emotion percentages
    sentiment_volatility = models.FloatField(null=True)

    # Topic Analysis
    topic_clusters = models.JSONField(default=dict)  # Topic modeling results
    keyword_frequency = models.JSONField(default=dict)  # Most frequent words
    themes_evolution = models.JSONField(default=dict)  # How themes change over time

    # Writing Patterns
    writing_patterns = models.JSONField(default=dict)  # Time, length, frequency
    linguistic_features = models.JSONField(default=dict)  # Style analysis
    readability_scores = models.JSONField(default=dict)  # Text complexity

    # Therapeutic Insights
    therapeutic_progress = models.JSONField(default=dict)  # Progress indicators
    coping_strategies_mentioned = ArrayField(
        models.CharField(max_length=100), default=list
    )
    goals_and_intentions = models.JSONField(default=list)

    # Cache Metadata
    cache_version = models.CharField(max_length=10, default="1.0")
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
            models.Index(fields=["expires_at"]),
        ]


class CommunicationMetrics(models.Model):
    """Aggregated communication pattern metrics"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    period_start = models.DateField()
    period_end = models.DateField()

    # Message Statistics
    total_messages_sent = models.IntegerField(default=0)
    total_messages_received = models.IntegerField(default=0)
    avg_message_length = models.FloatField(null=True)
    response_rate = models.FloatField(null=True)  # % of messages responded to

    # Timing Patterns
    avg_response_time_hours = models.FloatField(null=True)
    most_active_hour = models.IntegerField(null=True)
    communication_consistency = models.FloatField(null=True)

    # Therapeutic Relationship Metrics
    therapist_conversations = models.IntegerField(default=0)
    peer_conversations = models.IntegerField(default=0)
    support_seeking_score = models.FloatField(null=True)  # How often they seek help
    support_giving_score = models.FloatField(null=True)  # How often they help others

    # Content Analysis
    sentiment_distribution = models.JSONField(default=dict)
    emotional_expression_score = models.FloatField(null=True)
    topic_diversity = models.FloatField(null=True)
    crisis_language_detected = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "period_start"]
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["user", "-period_start"]),
            models.Index(fields=["crisis_language_detected"]),
        ]


class FeatureUsageMetrics(models.Model):
    """Track how users interact with different app features"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()

    # Core Feature Usage
    mood_logs_created = models.IntegerField(default=0)
    journal_entries_created = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    appointments_scheduled = models.IntegerField(default=0)

    # Engagement Metrics
    session_count = models.IntegerField(default=0)
    total_time_spent_minutes = models.IntegerField(default=0)
    features_used = ArrayField(models.CharField(max_length=50), default=list)

    # Therapeutic Tools Usage
    breathing_exercises_completed = models.IntegerField(default=0)
    coping_strategies_accessed = models.IntegerField(default=0)
    crisis_resources_accessed = models.IntegerField(default=0)

    # Social Features
    posts_created = models.IntegerField(default=0)
    comments_made = models.IntegerField(default=0)
    likes_given = models.IntegerField(default=0)

    # AI Interactions
    chatbot_conversations = models.IntegerField(default=0)
    ai_recommendations_viewed = models.IntegerField(default=0)
    ai_insights_acknowledged = models.IntegerField(default=0)

    class Meta:
        unique_together = ["user", "date"]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["date"]),
        ]


class PredictiveModel(models.Model):
    """Track predictive models and their performance"""

    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(
        max_length=50,
        choices=[
            ("mood_prediction", "Mood Prediction"),
            ("crisis_detection", "Crisis Detection"),
            ("engagement_prediction", "Engagement Prediction"),
            ("outcome_prediction", "Therapy Outcome Prediction"),
        ],
    )
    version = models.CharField(max_length=20)

    # Model Metadata
    features_used = ArrayField(models.CharField(max_length=100), default=list)
    hyperparameters = models.JSONField(default=dict)
    training_data_size = models.IntegerField()
    training_date = models.DateTimeField()

    # Performance Metrics
    accuracy = models.FloatField(null=True)
    precision = models.FloatField(null=True)
    recall = models.FloatField(null=True)
    f1_score = models.FloatField(null=True)
    auc_score = models.FloatField(null=True)

    # Model Status
    is_active = models.BooleanField(default=False)
    is_production = models.BooleanField(default=False)

    # Files and Storage
    model_path = models.CharField(max_length=500)  # Path to serialized model
    feature_importance = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_type", "is_active"]),
            models.Index(fields=["is_production"]),
        ]


class DataQualityReport(models.Model):
    """Track data quality metrics across the warehouse"""

    report_date = models.DateField(unique=True)

    # Completeness Metrics
    users_with_mood_data = models.IntegerField(default=0)
    users_with_journal_data = models.IntegerField(default=0)
    users_with_communication_data = models.IntegerField(default=0)
    data_completeness_score = models.FloatField()  # Overall completeness 0-1

    # Freshness Metrics
    avg_data_age_hours = models.FloatField()
    stale_records_count = models.IntegerField(default=0)

    # Consistency Metrics
    duplicate_records_found = models.IntegerField(default=0)
    inconsistency_issues = models.JSONField(default=list)

    # Volume Metrics
    total_records_processed = models.IntegerField(default=0)
    new_records_today = models.IntegerField(default=0)

    # Issues and Alerts
    critical_issues = models.JSONField(default=list)
    warnings = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-report_date"]
        indexes = [
            models.Index(fields=["-report_date"]),
            models.Index(fields=["data_completeness_score"]),
        ]


class AIAnalysisDataset(models.Model):
    """AI-ready aggregated dataset for analysis consumption"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    collection_date = models.DateTimeField(auto_now_add=True)
    period_days = models.IntegerField()

    # Aggregated data ready for AI consumption
    mood_summary = models.JSONField(default=dict, help_text="Processed mood analytics")
    journal_insights = models.JSONField(
        default=dict, help_text="Processed journal data"
    )
    behavioral_patterns = models.JSONField(
        default=dict, help_text="User behavior analytics"
    )
    communication_metrics = models.JSONField(
        default=dict, help_text="Communication data"
    )
    therapy_session_data = models.JSONField(
        default=dict, help_text="Therapy session analytics"
    )
    social_engagement_data = models.JSONField(
        default=dict, help_text="Social feeds analytics"
    )

    # Comprehensive analytics ready for AI
    risk_indicators = models.JSONField(
        default=dict, help_text="Risk assessment indicators"
    )
    progress_markers = models.JSONField(
        default=dict, help_text="Therapeutic progress markers"
    )
    pattern_analysis = models.JSONField(
        default=dict, help_text="Behavioral and mood patterns"
    )
    correlation_data = models.JSONField(
        default=dict, help_text="Cross-domain correlations"
    )

    # Data quality metrics
    data_completeness_score = models.FloatField(
        default=0.0, help_text="0-1 score of data completeness"
    )
    data_quality_indicators = models.JSONField(
        default=dict, help_text="Quality metrics per data source"
    )
    confidence_score = models.FloatField(
        default=0.0, help_text="Confidence in analysis reliability"
    )

    # Processing metadata
    processing_version = models.CharField(max_length=20, default="1.0")
    data_sources_used = ArrayField(models.CharField(max_length=50), default=list)
    processing_duration_seconds = models.FloatField(null=True)

    # Analysis readiness flags
    ready_for_mood_analysis = models.BooleanField(default=False)
    ready_for_journal_analysis = models.BooleanField(default=False)
    ready_for_behavior_analysis = models.BooleanField(default=False)
    ready_for_communication_analysis = models.BooleanField(default=False)
    ready_for_therapy_analysis = models.BooleanField(default=False)

    # Cache and expiration
    expires_at = models.DateTimeField(help_text="When this dataset expires")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["user", "period_days", "collection_date"]
        ordering = ["-collection_date"]
        indexes = [
            models.Index(fields=["user", "-collection_date"]),
            models.Index(fields=["expires_at", "is_active"]),
            models.Index(fields=["data_completeness_score"]),
            models.Index(
                fields=["ready_for_mood_analysis", "ready_for_journal_analysis"]
            ),
        ]

    def __str__(self):
        return f"AI Dataset for {self.user.username} ({self.period_days}d) - {self.collection_date.date()}"

    def is_expired(self):
        """Check if this dataset has expired"""
        return timezone.now() > self.expires_at

    def get_analysis_readiness(self):
        """Get summary of what analysis types this dataset supports"""
        return {
            "mood_analysis": self.ready_for_mood_analysis,
            "journal_analysis": self.ready_for_journal_analysis,
            "behavior_analysis": self.ready_for_behavior_analysis,
            "communication_analysis": self.ready_for_communication_analysis,
            "therapy_analysis": self.ready_for_therapy_analysis,
            "overall_score": self.data_completeness_score,
        }


class DataProcessingQueue(models.Model):
    """Queue for managing AI dataset processing jobs"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    period_days = models.IntegerField()
    analysis_types = ArrayField(models.CharField(max_length=50), default=list)

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )

    priority = models.CharField(
        max_length=10,
        choices=[
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="normal",
    )

    # Processing details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    result_dataset = models.ForeignKey(
        AIAnalysisDataset, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Processing metadata
    processing_attempts = models.IntegerField(default=0)
    estimated_duration_seconds = models.IntegerField(null=True)
    actual_duration_seconds = models.IntegerField(null=True)

    class Meta:
        ordering = ["-priority", "-requested_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["user", "-requested_at"]),
        ]

    def __str__(self):
        return f"Processing Queue: {self.user.username} ({self.status})"


class AIDataQualityReport(models.Model):
    """Reports on data quality for AI analysis"""

    dataset = models.OneToOneField(AIAnalysisDataset, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)

    # Data source quality scores (0-1)
    mood_data_quality = models.FloatField(default=0.0)
    journal_data_quality = models.FloatField(default=0.0)
    behavior_data_quality = models.FloatField(default=0.0)
    communication_data_quality = models.FloatField(default=0.0)
    therapy_data_quality = models.FloatField(default=0.0)

    # Completeness metrics
    data_coverage_percentage = models.FloatField(default=0.0)
    temporal_coverage_score = models.FloatField(default=0.0)

    # Data issues
    missing_data_indicators = models.JSONField(default=dict)
    data_inconsistencies = models.JSONField(default=list)
    outliers_detected = models.JSONField(default=list)

    # Recommendations
    quality_recommendations = models.JSONField(default=list)
    minimum_additional_data_needed = models.JSONField(default=dict)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"Quality Report for {self.dataset.user.username} - Score: {self.dataset.data_completeness_score:.2f}"


# New models from security services

class DataClassification(models.TextChoices):
    """Data classification levels for HIPAA/GDPR compliance"""
    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    CONFIDENTIAL = "confidential", "Confidential"
    RESTRICTED = "restricted", "Restricted"
    PHI = "phi", "Protected Health Information"


class ComplianceStandard(models.TextChoices):
    """Compliance standards"""
    HIPAA = "hipaa", "HIPAA"
    GDPR = "gdpr", "GDPR"
    SOC2 = "soc2", "SOC 2"
    ISO27001 = "iso27001", "ISO 27001"


class AuditEventType(models.TextChoices):
    """Types of audit events"""
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    ACCESS = "access", "Access"
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    EXPORT = "export", "Data Export"
    IMPORT = "import", "Data Import"
    BACKUP = "backup", "Backup"
    RESTORE = "restore", "Restore"


class AuditSeverity(models.TextChoices):
    """Audit event severity levels"""
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class EncryptionKey(models.Model):
    """Encryption key management with rotation capability"""
    
    key_id = models.CharField(max_length=64, unique=True)
    encrypted_key = models.TextField()
    algorithm = models.CharField(max_length=50, default="fernet")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    rotation_schedule = models.CharField(max_length=20, default="quarterly")
    
    class Meta:
        db_table = 'datawarehouse_encryption_key'
        indexes = [
            models.Index(fields=['key_id', 'is_active']),
            models.Index(fields=['expires_at']),
        ]


class DataClassificationRule(models.Model):
    """Rules for automatic data classification"""
    
    model_name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    classification = models.CharField(
        max_length=20, 
        choices=DataClassification.choices,
        default=DataClassification.INTERNAL
    )
    compliance_requirements = models.JSONField(default=list)
    encryption_required = models.BooleanField(default=False)
    access_restrictions = models.JSONField(default=dict)
    classified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_data_classification'
        unique_together = ['model_name', 'field_name']


class AccessLog(models.Model):
    """Comprehensive access logging for security monitoring"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    action = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    session_id = models.CharField(max_length=100)
    access_granted = models.BooleanField()
    denial_reason = models.TextField(blank=True)
    classification_level = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
        null=True
    )
    compliance_context = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_access_log'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['resource_type', 'action']),
            models.Index(fields=['ip_address', 'created_at']),
        ]


class AuditLog(models.Model):
    """Comprehensive audit logging for all system events"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=20, choices=AuditEventType.choices)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.CharField(max_length=255, null=True)
    event_name = models.CharField(max_length=200)
    description = models.TextField()
    metadata = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=10, choices=AuditSeverity.choices, default=AuditSeverity.LOW)
    compliance_tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    integrity_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['severity', 'created_at']),
        ]


class DataChangeHistory(models.Model):
    """Detailed field-level change history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_log = models.ForeignKey(AuditLog, on_delete=models.CASCADE, related_name='field_changes')
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)
    value_type = models.CharField(max_length=50)
    is_encrypted = models.BooleanField(default=False)
    encryption_key_id = models.CharField(max_length=64, blank=True)
    change_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_data_change_history'
        indexes = [
            models.Index(fields=['audit_log', 'field_name']),
            models.Index(fields=['created_at']),
        ]


class BackupType(models.TextChoices):
    """Types of backups"""
    FULL = "full", "Full Backup"
    INCREMENTAL = "incremental", "Incremental Backup"
    DIFFERENTIAL = "differential", "Differential Backup"
    SNAPSHOT = "snapshot", "Database Snapshot"
    SELECTIVE = "selective", "Selective Backup"


class BackupStatus(models.TextChoices):
    """Backup job status"""
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class BackupJob(models.Model):
    """Backup job tracking and management"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_type = models.CharField(max_length=20, choices=BackupType.choices)
    status = models.CharField(max_length=20, choices=BackupStatus.choices, default=BackupStatus.PENDING)
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    scheduled = models.BooleanField(default=False)
    schedule_name = models.CharField(max_length=100, blank=True)
    
    # Storage information
    storage_location = models.CharField(max_length=500)
    storage_type = models.CharField(max_length=50, default="local")  # local, s3, azure, etc.
    file_size = models.BigIntegerField(null=True)
    compressed_size = models.BigIntegerField(null=True)
    compression_ratio = models.FloatField(null=True)
    
    # Encryption and security
    is_encrypted = models.BooleanField(default=True)
    encryption_key_id = models.CharField(max_length=64, blank=True)
    integrity_hash = models.CharField(max_length=128)
    
    # Timing information
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    duration_seconds = models.IntegerField(null=True)
    
    # Backup scope and metadata
    included_models = ArrayField(models.CharField(max_length=100), default=list)
    excluded_models = ArrayField(models.CharField(max_length=100), default=list)
    record_count = models.BigIntegerField(null=True)
    metadata = models.JSONField(default=dict)
    
    # Retention and cleanup
    retention_days = models.IntegerField(default=30)
    expires_at = models.DateTimeField()
    auto_cleanup = models.BooleanField(default=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'datawarehouse_backup_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'backup_type']),
            models.Index(fields=['scheduled', 'created_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['initiated_by', 'created_at']),
        ]


class RestoreJob(models.Model):
    """Restore job tracking and management"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_job = models.ForeignKey(BackupJob, on_delete=models.CASCADE, related_name='restore_jobs')
    restore_type = models.CharField(
        max_length=20,
        choices=[
            ('full', 'Full Restore'),
            ('partial', 'Partial Restore'),
            ('selective', 'Selective Restore'),
            ('point_in_time', 'Point-in-Time Restore'),
        ]
    )
    status = models.CharField(max_length=20, choices=BackupStatus.choices, default=BackupStatus.PENDING)
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Target information
    target_environment = models.CharField(max_length=50, default="current")
    target_database = models.CharField(max_length=100, blank=True)
    
    # Restore scope
    included_models = ArrayField(models.CharField(max_length=100), default=list)
    excluded_models = ArrayField(models.CharField(max_length=100), default=list)
    restore_point = models.DateTimeField(null=True)
    
    # Progress tracking
    total_records = models.BigIntegerField(null=True)
    processed_records = models.BigIntegerField(default=0)
    failed_records = models.BigIntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    duration_seconds = models.IntegerField(null=True)
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('passed', 'Passed'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        default='pending'
    )
    verification_details = models.JSONField(default=dict)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'datawarehouse_restore_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['backup_job', 'status']),
            models.Index(fields=['initiated_by', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

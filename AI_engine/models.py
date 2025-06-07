# AI_engine/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class UserAnalysis(models.Model):
    """Stores AI-generated analysis of user's mood and journal data"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateField(default=timezone.now)
    mood_score = models.FloatField(help_text="Aggregated mood score from -1 to 1")
    sentiment_score = models.FloatField(
        help_text="Journal content sentiment score from -1 to 1"
    )
    dominant_emotions = models.JSONField(
        default=list, help_text="List of dominant emotions detected"
    )
    topics_of_concern = models.JSONField(
        default=list, help_text="Key topics or concerns identified"
    )
    suggested_activities = models.JSONField(
        default=list, help_text="AI-suggested activities"
    )
    risk_factors = models.JSONField(
        default=dict, help_text="Identified risk factors and levels"
    )
    improvement_metrics = models.JSONField(
        default=dict, help_text="Metrics showing user's improvement"
    )

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
            models.Index(fields=["mood_score"]),
        ]


class AIInsight(models.Model):
    """Stores specific AI insights for chatbot context"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    insight_type = models.CharField(
        max_length=50,
        choices=[
            ("mood_pattern", "Mood Pattern"),
            ("behavioral_change", "Behavioral Change"),
            ("journal_theme", "Journal Theme"),
            ("activity_impact", "Activity Impact"),
            ("risk_alert", "Risk Alert"),
        ],
    )
    insight_data = models.JSONField(help_text="Structured insight data")
    priority = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="medium",
    )
    is_addressed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-priority"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["insight_type", "priority"]),
        ]


class TherapyRecommendation(models.Model):
    """Model for storing AI-generated therapy recommendations"""

    RECOMMENDATION_TYPES = [
        ("activity_suggestion", "Activity Suggestion"),
        ("coping_strategy", "Coping Strategy"),
        ("intervention", "Intervention"),
        ("referral", "Referral"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapy_recommendations",
    )
    recommendation_type = models.CharField(max_length=50, choices=RECOMMENDATION_TYPES)
    recommendation_data = models.JSONField()
    context_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["recommendation_type"]),
        ]

    def __str__(self):
        return f"{self.recommendation_type} for {self.user.username}"


class SocialInteractionAnalysis(models.Model):
    """Analyzes user interactions in feeds to detect patterns"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateField(default=timezone.now)
    engagement_score = models.FloatField(
        help_text="Score representing user's social engagement level"
    )
    interaction_patterns = models.JSONField(
        default=dict, help_text="Patterns of user interactions"
    )
    therapeutic_content = models.JSONField(
        default=list, help_text="Content that has therapeutic value for user"
    )
    support_network = models.JSONField(
        default=dict, help_text="Analysis of user's support network"
    )
    content_preferences = models.JSONField(
        default=dict, help_text="Content types user engages with most"
    )
    mood_correlation = models.JSONField(
        default=dict, help_text="Correlation between social activity and mood"
    )
    growth_areas = models.JSONField(
        default=list, help_text="Areas for growth and improvement"
    )
    suggested_interventions = models.JSONField(
        default=list, help_text="Suggested interventions"
    )

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
            models.Index(fields=["engagement_score"]),
        ]


class CommunicationPatternAnalysis(models.Model):
    """Analyzes messaging patterns between users"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateField(default=timezone.now)
    therapeutic_relationships = models.JSONField(
        default=dict, help_text="Analysis of user's therapeutic relationships"
    )
    conversation_metrics = models.JSONField(
        default=dict, help_text="Metrics about conversation patterns"
    )
    communication_style = models.JSONField(
        default=dict, help_text="User's communication style characteristics"
    )
    response_patterns = models.JSONField(
        default=dict, help_text="Patterns in how user responds to different approaches"
    )
    emotional_triggers = models.JSONField(
        default=list, help_text="Topics that trigger emotional responses"
    )
    improvement_areas = models.JSONField(
        default=list, help_text="Areas where communication could be improved"
    )
    engagement_score = models.FloatField(
        default=0.0, help_text="Overall engagement score"
    )
    ai_insights = models.JSONField(
        default=dict, help_text="AI-generated insights about communication patterns"
    )

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
            models.Index(fields=["engagement_score"]),
        ]

    def __str__(self):
        return (
            f"Communication Analysis for {self.user.username} on {self.analysis_date}"
        )


class ConversationSummary(models.Model):
    """Stores AI-generated summaries of older conversation parts"""

    conversation_id = models.CharField(max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    start_message_id = models.CharField(max_length=255)
    end_message_id = models.CharField(max_length=255)
    message_count = models.IntegerField()
    summary_text = models.TextField(
        help_text="AI-generated summary of conversation segment"
    )
    key_points = models.JSONField(
        default=list, help_text="Key points from the conversation"
    )
    emotional_context = models.JSONField(
        default=dict, help_text="Emotional context of conversation"
    )

    class Meta:
        ordering = ["conversation_id", "created_at"]
        indexes = [
            models.Index(fields=["conversation_id"]),
            models.Index(fields=["user", "conversation_id"]),
        ]


class MedicationEffectAnalysis(models.Model):
    """Tracks effects of medications on mood and behavior"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateField(default=timezone.now)
    medications = models.JSONField(
        default=list, help_text="Current medications being analyzed"
    )
    mood_effects = models.JSONField(default=dict, help_text="Effects on mood")
    side_effects_detected = models.JSONField(
        default=list, help_text="Potential side effects detected"
    )
    adherence_patterns = models.JSONField(
        default=dict, help_text="Medication adherence patterns"
    )
    recommendations = models.JSONField(
        default=list, help_text="AI recommendations regarding medication"
    )

    def _analyze_mood_trends(self, mood_tracking, medication_changes):
        """Analyze mood trends around medication changes"""
        try:
            trends = {}
            correlation_score = 0
            significant_changes = []

            # Simple trend analysis
            for change in medication_changes:
                date = change["date"]
                if date in mood_tracking:
                    # Calculate trend around this date
                    trends[date] = {
                        "before_mood": 0,
                        "after_mood": 0,
                        "change_detected": True,
                    }

            return {
                "trends": trends,
                "correlation_score": correlation_score,
                "significant_changes": significant_changes,
            }
        except Exception:
            return {"trends": {}, "correlation_score": 0, "significant_changes": []}

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
        ]


class CrisisEvent(models.Model):
    """Model to track crisis detection events"""

    CRISIS_LEVELS = [
        ("low", "Low Risk"),
        ("medium", "Medium Risk"),
        ("high", "High Risk"),
        ("critical", "Critical Risk"),
    ]

    user = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, related_name="crisis_events"
    )
    message_content = models.TextField(
        help_text="Truncated content of the triggering message"
    )
    confidence = models.FloatField(help_text="AI confidence score for crisis detection")
    crisis_level = models.CharField(max_length=20, choices=CRISIS_LEVELS)
    matched_terms = models.JSONField(
        default=list, help_text="Terms that triggered crisis detection"
    )
    category = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True, null=True)
    staff_notified = models.BooleanField(default=False)
    follow_up_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Crisis Event"
        verbose_name_plural = "Crisis Events"

    def __str__(self):
        return f"Crisis Event - {self.user.username} - {self.crisis_level} - {self.timestamp}"

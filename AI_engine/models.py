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
    """AI-generated therapy recommendations"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    recommendation_type = models.CharField(
        max_length=50,
        choices=[
            ("coping_strategy", "Coping Strategy"),
            ("activity_suggestion", "Activity Suggestion"),
            ("resource_referral", "Resource Referral"),
            ("intervention", "Intervention"),
        ],
    )
    recommendation_data = models.JSONField(help_text="Structured recommendation data")
    context_data = models.JSONField(
        help_text="Context that triggered this recommendation"
    )
    is_implemented = models.BooleanField(default=False)
    effectiveness_rating = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["recommendation_type"]),
        ]


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

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
        ]


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

    class Meta:
        ordering = ["-analysis_date"]
        indexes = [
            models.Index(fields=["user", "-analysis_date"]),
        ]

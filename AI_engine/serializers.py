# AI_engine/serializers.py
from rest_framework import serializers
from .models import (
    UserAnalysis,
    AIInsight,
    TherapyRecommendation,
    CommunicationPatternAnalysis,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnalysis
        fields = [
            "id",
            "user",
            "analysis_date",
            "mood_score",
            "sentiment_score",
            "dominant_emotions",
            "topics_of_concern",
            "suggested_activities",
            "risk_factors",
            "improvement_metrics",
        ]
        read_only_fields = ["user", "analysis_date"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class AIInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIInsight
        fields = [
            "id",
            "user",
            "created_at",
            "insight_type",
            "insight_data",
            "priority",
            "is_addressed",
        ]
        read_only_fields = ["user", "created_at"]


class TherapyRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapyRecommendation
        fields = [
            "id",
            "user",
            "created_at",
            "recommendation_type",
            "recommendation_data",
            "context_data",
            "is_implemented",
            "effectiveness_rating",
        ]
        read_only_fields = ["user", "created_at"]


class CommunicationPatternAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationPatternAnalysis
        fields = [
            "id",
            "user",
            "analysis_date",
            "therapeutic_relationships",
            "conversation_metrics",
            "communication_style",
            "response_patterns",
            "emotional_triggers",
            "improvement_areas",
        ]
        read_only_fields = ["user", "analysis_date"]


class UserResumeSerializer(serializers.Serializer):
    """Serializer for user resume data"""

    user_id = serializers.IntegerField()
    user_info = serializers.DictField()
    period_info = serializers.DictField()
    analytics_cards = serializers.DictField()
    ai_therapist_summary = serializers.DictField()
    data_quality = serializers.DictField()
    last_updated = serializers.DateTimeField()


class MentalHealthCardSerializer(serializers.Serializer):
    """Serializer for Mental Health Overview card"""

    card_title = serializers.CharField()
    summary_metrics = serializers.DictField()
    dominant_emotions = serializers.ListField(child=serializers.CharField())
    mental_health_themes = serializers.ListField(child=serializers.CharField())
    risk_indicators = serializers.ListField(child=serializers.CharField())
    journal_sentiment_trend = serializers.CharField()
    mood_consistency_score = serializers.FloatField()
    needs_attention = serializers.BooleanField()
    data_points = serializers.DictField()


class BehavioralPatternsCardSerializer(serializers.Serializer):
    """Serializer for Behavioral Patterns card"""

    card_title = serializers.CharField()
    usage_metrics = serializers.DictField()
    activity_patterns = serializers.DictField()
    behavioral_insights = serializers.ListField(child=serializers.CharField())
    engagement_level = serializers.CharField()
    consistency_score = serializers.FloatField()
    feature_adoption_rate = serializers.FloatField()


class SocialEngagementCardSerializer(serializers.Serializer):
    """Serializer for Social Engagement card"""

    card_title = serializers.CharField()
    social_metrics = serializers.DictField()
    communication_patterns = serializers.DictField()
    social_insights = serializers.ListField(child=serializers.CharField())
    interaction_quality = serializers.CharField()
    community_involvement = serializers.CharField()
    support_seeking_behavior = serializers.CharField()


class ProgressTrackingCardSerializer(serializers.Serializer):
    """Serializer for Progress Tracking card"""

    card_title = serializers.CharField()
    progress_metrics = serializers.DictField()
    progress_indicators = serializers.DictField()
    progress_trends = serializers.ListField(child=serializers.CharField())
    recent_ai_recommendations = serializers.ListField(child=serializers.DictField())
    intervention_priorities = serializers.ListField(child=serializers.CharField())
    therapy_readiness = serializers.DictField()
    next_assessment_due = serializers.DateField()
    monitoring_alerts = serializers.ListField(child=serializers.CharField())


class AITherapistSummarySerializer(serializers.Serializer):
    """Serializer for AI Therapist Summary"""

    ai_summary = serializers.CharField()
    key_concerns = serializers.ListField(child=serializers.CharField())
    therapeutic_recommendations = serializers.ListField(child=serializers.CharField())
    session_focus_areas = serializers.ListField(child=serializers.CharField())
    clinical_insights = serializers.ListField(child=serializers.CharField())
    risk_assessment = serializers.CharField()
    intervention_suggestions = serializers.ListField(child=serializers.CharField())
    progress_observations = serializers.CharField()
    therapist_notes = serializers.CharField()
    generated_at = serializers.DateTimeField()
    ai_confidence_score = serializers.FloatField()

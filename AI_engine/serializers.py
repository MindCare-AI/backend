# AI_engine/serializers.py
from rest_framework import serializers
from .models import (
    UserAnalysis,
    AIInsight,
    TherapyRecommendation,
    CommunicationPatternAnalysis,
)


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
            "created_at",
            "pattern_type",
            "pattern_data",
            "analysis_summary",
        ]
        read_only_fields = ["user", "created_at"]

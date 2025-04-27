from django.contrib import admin
from .models import UserAnalysis, AIInsight, TherapyRecommendation

@admin.register(UserAnalysis)
class UserAnalysisAdmin(admin.ModelAdmin):
    list_display = ('user', 'analysis_date', 'mood_score', 'sentiment_score')
    list_filter = ('analysis_date', 'user')
    search_fields = ('user__username', 'user__email')
    date_hierarchy = 'analysis_date'
    readonly_fields = ('analysis_date',)

@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ('user', 'insight_type', 'priority', 'created_at', 'is_addressed')
    list_filter = ('insight_type', 'priority', 'is_addressed', 'created_at')
    search_fields = ('user__username', 'insight_data')
    readonly_fields = ('created_at',)

@admin.register(TherapyRecommendation)
class TherapyRecommendationAdmin(admin.ModelAdmin):
    list_display = ('user', 'recommendation_type', 'created_at', 'is_implemented', 'effectiveness_rating')
    list_filter = ('recommendation_type', 'is_implemented', 'created_at')
    search_fields = ('user__username', 'recommendation_data')
    readonly_fields = ('created_at',)

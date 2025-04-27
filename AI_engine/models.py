from django.db import models
from django.conf import settings
from django.utils import timezone

class UserAnalysis(models.Model):
    """Stores AI-generated analysis of user's mood and journal data"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    analysis_date = models.DateField(default=timezone.now)
    mood_score = models.FloatField(help_text="Aggregated mood score from -1 to 1")
    sentiment_score = models.FloatField(help_text="Journal content sentiment score from -1 to 1")
    dominant_emotions = models.JSONField(default=list, help_text="List of dominant emotions detected")
    topics_of_concern = models.JSONField(default=list, help_text="Key topics or concerns identified")
    suggested_activities = models.JSONField(default=list, help_text="AI-suggested activities")
    risk_factors = models.JSONField(default=dict, help_text="Identified risk factors and levels")
    improvement_metrics = models.JSONField(default=dict, help_text="Metrics showing user's improvement")
    
    class Meta:
        ordering = ['-analysis_date']
        indexes = [
            models.Index(fields=['user', '-analysis_date']),
            models.Index(fields=['mood_score']),
        ]

class AIInsight(models.Model):
    """Stores specific AI insights for chatbot context"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    insight_type = models.CharField(max_length=50, choices=[
        ('mood_pattern', 'Mood Pattern'),
        ('behavioral_change', 'Behavioral Change'),
        ('journal_theme', 'Journal Theme'),
        ('activity_impact', 'Activity Impact'),
        ('risk_alert', 'Risk Alert'),
    ])
    insight_data = models.JSONField(help_text="Structured insight data")
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], default='medium')
    is_addressed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at', '-priority']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['insight_type', 'priority']),
        ]

class TherapyRecommendation(models.Model):
    """AI-generated therapy recommendations"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    recommendation_type = models.CharField(max_length=50, choices=[
        ('coping_strategy', 'Coping Strategy'),
        ('activity_suggestion', 'Activity Suggestion'),
        ('resource_referral', 'Resource Referral'),
        ('intervention', 'Intervention'),
    ])
    recommendation_data = models.JSONField(help_text="Structured recommendation data")
    context_data = models.JSONField(help_text="Context that triggered this recommendation")
    is_implemented = models.BooleanField(default=False)
    effectiveness_rating = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['recommendation_type']),
        ]

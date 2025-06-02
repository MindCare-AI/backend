# AI_engine/urls.py
from django.urls import path
from rest_framework import routers
from .views import (
    AIAnalysisViewSet,
    AIInsightViewSet,
    TherapyRecommendationViewSet,
    CommunicationAnalysisViewSet,
    TipsViewSet,
)
from . import views  # Import views for user resume endpoints

# Create router only for the AIAnalysisViewSet which is a full ModelViewSet
router = routers.DefaultRouter()
router.register(r"analysis", AIAnalysisViewSet, basename="ai-analysis")

urlpatterns = [
    # AI Insights endpoints with explicitly defined actions
    path(
        "insights/",
        AIInsightViewSet.as_view({"get": "list"}),
        name="ai-insights-list",
    ),
    path(
        "insights/<int:pk>/",
        AIInsightViewSet.as_view({"get": "retrieve"}),
        name="ai-insights-detail",
    ),
    path(
        "insights/<int:pk>/mark-addressed/",
        AIInsightViewSet.as_view({"post": "mark_addressed"}),
        name="ai-insights-mark-addressed",
    ),
    path(
        "insights/chatbot-context/",
        AIInsightViewSet.as_view({"get": "chatbot_context"}),
        name="ai-insights-chatbot-context",
    ),
    path(
        "insights/analyze-user/",
        AIInsightViewSet.as_view({"post": "analyze_user"}),
        name="ai-insights-analyze-user",
    ),
    # Therapy Recommendations endpoints
    path(
        "recommendations/",
        TherapyRecommendationViewSet.as_view({"get": "list"}),
        name="ai-recommendations-list",
    ),
    path(
        "recommendations/<int:pk>/",
        TherapyRecommendationViewSet.as_view({"get": "retrieve"}),
        name="ai-recommendations-detail",
    ),
    path(
        "recommendations/<int:pk>/mark-implemented/",
        TherapyRecommendationViewSet.as_view({"post": "mark_implemented"}),
        name="ai-recommendations-mark-implemented",
    ),
    path(
        "recommendations/<int:pk>/rate/",
        TherapyRecommendationViewSet.as_view({"post": "rate_effectiveness"}),
        name="ai-recommendations-rate",
    ),
    # Communication Analysis endpoints - CUSTOM ACTIONS FIRST
    path(
        "communication/analyze-patterns/",
        CommunicationAnalysisViewSet.as_view({"post": "analyze_patterns"}),
        name="ai-communication-analyze-patterns",
    ),
    path(
        "communication/analyze-user/",
        CommunicationAnalysisViewSet.as_view({"post": "analyze_user"}),
        name="ai-communication-analyze-user",
    ),
    path(
        "communication/therapeutic-relationship/",
        CommunicationAnalysisViewSet.as_view({"get": "therapeutic_relationship"}),
        name="ai-communication-therapeutic-relationship",
    ),
    path(
        "communication/",
        CommunicationAnalysisViewSet.as_view({"get": "list"}),
        name="ai-communication-list",
    ),
    path(
        "communication/<int:pk>/",
        CommunicationAnalysisViewSet.as_view({"get": "retrieve"}),
        name="ai-communication-detail",
    ),
    # Tips endpoints
    path(
        "tips/mood/",
        TipsViewSet.as_view({"get": "mood"}),
        name="ai-tips-mood",
    ),
    path(
        "tips/journaling/",
        TipsViewSet.as_view({"get": "journaling"}),
        name="ai-tips-journaling",
    ),
    path(
        "tips/combined/",
        TipsViewSet.as_view({"get": "combined"}),
        name="ai-tips-combined",
    ),
    # User Resume endpoints for therapists
    path('resume/<int:id>/', views.user_resume_view, name='user-resume'),
    path('resume/<int:id>/card/<str:card_type>/', views.user_analytics_card_view, name='user-analytics-card'),
]

# Add the router's URLs to our urlpatterns
urlpatterns += router.urls

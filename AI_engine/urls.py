# AI_engine/urls.py
from django.urls import path
from rest_framework import routers
from .views import AIAnalysisViewSet, AIInsightViewSet, TherapyRecommendationViewSet

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
]

# Add the router's URLs to our urlpatterns
urlpatterns += router.urls

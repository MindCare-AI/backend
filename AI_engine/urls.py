#AI_engine/urls.py
from django.urls import path
from .views import AIInsightViewSet, TherapyRecommendationViewSet

urlpatterns = [
    # AI Insights endpoints
    path(
        "insights/",
        AIInsightViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-insights-list",
    ),
    path(
        "insights/<int:pk>/",
        AIInsightViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="ai-insights-detail",
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
        TherapyRecommendationViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-recommendations-list",
    ),
    path(
        "recommendations/<int:pk>/",
        TherapyRecommendationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="ai-recommendations-detail",
    ),
    path(
        "recommendations/<int:pk>/rate/",
        TherapyRecommendationViewSet.as_view({"post": "rate_effectiveness"}),
        name="ai-recommendations-rate",
    ),
]

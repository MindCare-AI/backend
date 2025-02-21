from django.urls import path
from . import views

urlpatterns = [
    path("engagement/", views.user_engagement_view, name="user_engagement"),
    path("health-insights/", views.health_insights_view, name="health_insights"),
    path("crisis-prediction/", views.crisis_prediction_view, name="crisis_prediction"),
]

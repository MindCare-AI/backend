from django.urls import path
from . import views

urlpatterns = [
    path("entry/", views.mood_entry_view, name="mood_entry"),
    path("patterns/", views.mood_patterns_view, name="mood_patterns"),
    path("voice-analysis/", views.voice_analysis_view, name="voice_analysis"),
]

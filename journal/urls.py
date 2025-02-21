from django.urls import path
from . import views

urlpatterns = [
    path("entries/", views.journal_entries_view, name="journal_entries"),
    path("voice-journal/", views.voice_journal_view, name="voice_journal"),
    path("prompts/", views.prompts_view, name="prompts"),
]

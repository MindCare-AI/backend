from django.urls import path
from . import views

urlpatterns = [
    path("exercises/", views.exercises_view, name="exercises"),
    path("progress/", views.progress_view, name="progress"),
    path("goals/", views.goals_view, name="goals"),
    path("templates/", views.activity_templates_view, name="activity_templates"),
    path("schedules/", views.activity_schedules_view, name="activity_schedules"),
]

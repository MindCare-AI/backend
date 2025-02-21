from django.urls import path
from . import views

urlpatterns = [
    path("alerts/", views.alerts_view, name="alerts"),
    path("reminders/", views.reminders_view, name="reminders"),
    path("achievements/", views.achievements_view, name="achievements"),
]

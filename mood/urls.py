#mood/urls.py
from django.urls import path
from mood.views import MoodLogViewSet

urlpatterns = [
    path("mood-logs/", MoodLogViewSet.as_view({"get": "list", "post": "create"}), name="mood-log-list"),
    path("mood-logs/<int:pk>/", MoodLogViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="mood-log-detail"),
]

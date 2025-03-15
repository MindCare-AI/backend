# patient/urls.py
from django.urls import path
from .views import PatientProfileViewSet, MoodLogViewSet  # Import MoodLogViewSet

urlpatterns = [
    # Patient Profiles (No POST allowed)
    path(
        "profiles/",
        PatientProfileViewSet.as_view({"get": "list"}),  # GET only
        name="patient-profile-list",
    ),
    path(
        "profiles/<int:pk>/",
        PatientProfileViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="patient-profile-detail",
    ),
    path(
        "profiles/<int:pk>/appointments/",
        PatientProfileViewSet.as_view({"get": "appointments"}),
        name="patient-appointments",
    ),

    # Mood Logs Endpoints
    path(
        "mood-logs/",
        MoodLogViewSet.as_view({"get": "list", "post": "create"}),
        name="mood-log-list",
    ),
    path(
        "mood-logs/<int:pk>/",
        MoodLogViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="mood-log-detail",
    ),
]

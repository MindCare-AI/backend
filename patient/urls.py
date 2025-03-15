# patient/urls.py
from django.urls import path
from .views import (
    PatientProfileViewSet, 
    MoodLogViewSet,
    HealthMetricViewSet,
    MedicalHistoryViewSet
)

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

    # Health Metrics Endpoints
    path(
        "health-metrics/",
        HealthMetricViewSet.as_view({"get": "list", "post": "create"}),
        name="health-metric-list",
    ),
    path(
        "health-metrics/<int:pk>/",
        HealthMetricViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "delete": "destroy"
        }),
        name="health-metric-detail",
    ),

    # Medical History Endpoints
    path(
        "medical-history/",
        MedicalHistoryViewSet.as_view({"get": "list", "post": "create"}),
        name="medical-history-list",
    ),
    path(
        "medical-history/<int:pk>/",
        MedicalHistoryViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "delete": "destroy"
        }),
        name="medical-history-detail",
    ),
]

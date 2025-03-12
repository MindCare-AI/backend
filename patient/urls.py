# patient/urls.py
from django.urls import path
from .views import PatientProfileViewSet

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
            {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
        ),
        name="patient-profile-detail",
    ),
    path(
        "profiles/<int:pk>/appointments/",
        PatientProfileViewSet.as_view({"get": "appointments"}),
        name="patient-appointments",
    ),
]

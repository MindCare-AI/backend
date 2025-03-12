# therapist/urls.py
from django.urls import path
from .views import TherapistProfileViewSet

urlpatterns = [
    # Therapist Profiles (No POST allowed)
    path(
        "profiles/",
        TherapistProfileViewSet.as_view({"get": "list"}),  # GET only
        name="therapist-profile-list",
    ),
    path(
        "profiles/<int:pk>/",
        TherapistProfileViewSet.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update"}
        ),
        name="therapist-profile-detail",
    ),
    # New Features
    path(
        "profiles/<int:pk>/availability/",
        TherapistProfileViewSet.as_view({"get": "availability"}),
        name="therapist-availability",
    ),
    path(
        "profiles/filter/",
        TherapistProfileViewSet.as_view({"get": "list"}),
        name="therapist-filter",
    ),
]

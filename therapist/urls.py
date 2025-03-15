# therapist/urls.py
from django.urls import path
from .views import (
    TherapistProfileViewSet,
    SessionNoteViewSet,
    ClientFeedbackViewSet,  # Add this import
)

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
    # update_availability endpoint
    path(
        "profiles/<int:pk>/update_availability/",
        TherapistProfileViewSet.as_view({"post": "update_availability"}),
        name="therapist-update-availability",
    ),
    # verify endpoint
    path(
        "profiles/<int:pk>/verify/",
        TherapistProfileViewSet.as_view({"post": "verify"}),
        name="therapist-verify",
    ),
    # Add book_appointment endpoint
    path(
        "profiles/<int:pk>/book_appointment/",
        TherapistProfileViewSet.as_view({"post": "book_appointment"}),
        name="therapist-book-appointment",
    ),
    # Add appointments endpoint
    path(
        "profiles/<int:pk>/appointments/",
        TherapistProfileViewSet.as_view({"get": "appointments"}),
        name="therapist-appointments",
    ),
    # New route for session notes
    path(
        "session-notes/",
        SessionNoteViewSet.as_view({"get": "list", "post": "create"}),
        name="therapist-session-notes",
    ),
    path(
        "session-notes/<int:pk>/",
        SessionNoteViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy"
        }),
        name="therapist-session-note-detail",
    ),
    # New routes for client feedback
    path(
        "client-feedback/",
        ClientFeedbackViewSet.as_view({"get": "list", "post": "create"}),
        name="therapist-client-feedback",
    ),
    path(
        "client-feedback/<int:pk>/",
        ClientFeedbackViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy"
        }),
        name="therapist-client-feedback-detail",
    ),
]

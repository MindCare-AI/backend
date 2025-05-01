# therapist/urls.py
from django.urls import path
from therapist.views.therapist_profile_views import (
    TherapistProfileViewSet,
    PublicTherapistListView,
)
from therapist.views.session_note_views import SessionNoteViewSet

urlpatterns = [
    # Therapist Profiles
    path(
        "profiles/",
        TherapistProfileViewSet.as_view({"get": "list", "post": "create"}),
        name="therapist-profiles",
    ),
    path(
        "profiles/<int:pk>/",
        TherapistProfileViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="therapist-profile-detail",
    ),
    # Therapist Profile Actions
    path(
        "profiles/<int:pk>/availability/",
        TherapistProfileViewSet.as_view(
            {
                "get": "availability",
                "post": "update_availability",
                "patch": "availability",
            }
        ),
        name="therapist-availability",
    ),
    path(
        "profiles/<int:pk>/verify/",
        TherapistProfileViewSet.as_view(
            {
                "get": "verify",  # allows GET to verify therapist
                "post": "verify"
            }
        ),
        name="therapist-verify",
    ),
    path(
        "profiles/all/",
        PublicTherapistListView.as_view(),
        name="public-therapist-list",
    ),
    # Session Notes
    path(
        "session-notes/",
        SessionNoteViewSet.as_view({"get": "list", "post": "create"}),
        name="session-notes-list",
    ),
    path(
        "session-notes/<int:pk>/",
        SessionNoteViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="session-notes-detail",
    ),
]

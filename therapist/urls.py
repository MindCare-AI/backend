# therapist/urls.py
from django.urls import path
from therapist.views.therapist_profile_views import (
    TherapistProfileViewSet,
    PublicTherapistListView,
)
from therapist.views.client_feedback_views import ClientFeedbackViewSet
from therapist.views.session_note_views import SessionNoteViewSet
from therapist.views.appointment_views import AppointmentViewSet

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
        "profiles/<int:pk>/book-appointment/",
        TherapistProfileViewSet.as_view({"post": "book_appointment"}),
        name="therapist-book-appointment",
    ),
    path(
        "profiles/<int:pk>/availability/",
        TherapistProfileViewSet.as_view(
            {"get": "availability", "post": "update_availability"}
        ),
        name="therapist-availability",
    ),
    path(
        "profiles/<int:pk>/verify/",
        TherapistProfileViewSet.as_view({"post": "verify"}),
        name="therapist-verify",
    ),
    path(
        "profiles/<int:pk>/appointments/",
        TherapistProfileViewSet.as_view({"get": "appointments"}),
        name="therapist-appointments",
    ),
    path(
        "profiles/all/",
        PublicTherapistListView.as_view(),
        name="public-therapist-list",
    ),
    # Appointments
    path(
        "appointments/",
        AppointmentViewSet.as_view({"get": "list", "post": "create"}),
        name="appointment-list",
    ),
    path(
        "appointments/<int:pk>/",
        AppointmentViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="appointment-detail",
    ),
    path(
        "appointments/<int:pk>/reschedule/",
        AppointmentViewSet.as_view({"post": "reschedule"}),
        name="appointment-reschedule",
    ),
    path(
        "appointments/<int:pk>/confirm/",
        AppointmentViewSet.as_view({"post": "confirm"}),
        name="appointment-confirm",
    ),
    # Client Feedback
    path(
        "client-feedback/",
        ClientFeedbackViewSet.as_view({"get": "list", "post": "create"}),
        name="client-feedback-list",
    ),
    path(
        "client-feedback/<int:pk>/",
        ClientFeedbackViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="client-feedback-detail",
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

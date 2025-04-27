from django.urls import path
from .views import AppointmentViewSet, WaitingListEntryViewSet

urlpatterns = [
    # Appointment URLs
    path(
        "",
        AppointmentViewSet.as_view({"get": "list", "post": "create"}),
        name="appointment-list",
    ),
    path(
        "<int:pk>/",
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
        "<int:pk>/cancel/",
        AppointmentViewSet.as_view({"post": "cancel"}),
        name="appointment-cancel",
    ),
    path(
        "<int:pk>/confirm/",
        AppointmentViewSet.as_view({"post": "confirm"}),
        name="appointment-confirm",
    ),
    path(
        "<int:pk>/complete/",
        AppointmentViewSet.as_view({"post": "complete"}),
        name="appointment-complete",
    ),
    # Waiting List URLs
    path(
        "waiting-list/",
        WaitingListEntryViewSet.as_view({"get": "list", "post": "create"}),
        name="waiting-list",
    ),
    path(
        "waiting-list/<int:pk>/",
        WaitingListEntryViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="waiting-list-detail",
    ),
    path(
        "waiting-list/check-availability/",
        WaitingListEntryViewSet.as_view({"get": "check_availability"}),
        name="waiting-list-check",
    ),
    path(
        "waiting-list/<int:pk>/cancel/",
        WaitingListEntryViewSet.as_view({"post": "cancel"}),
        name="waiting-list-cancel",
    ),
]

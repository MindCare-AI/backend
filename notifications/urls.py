# notifications/urls.py
from django.urls import path
from .views import NotificationViewSet, NotificationTypeViewSet

urlpatterns = [
    path("", NotificationViewSet.as_view({"get": "list"}), name="notification-list"),
    path(
        "<int:pk>/",  # Changed from <uuid:pk> to <int:pk>
        NotificationViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="notification-detail",
    ),
    path(
        "mark-all-read/",
        NotificationViewSet.as_view({"post": "mark_all_read"}),
        name="mark-all-read",
    ),
    path(
        "types/",
        NotificationTypeViewSet.as_view({"get": "list"}),
        name="notification-type-list",
    ),
    path(
        "count/",
        NotificationViewSet.as_view({"get": "count"}),
        name="notification-count",
    ),
    path(
        "bulk-delete/",
        NotificationViewSet.as_view({"post": "bulk_delete"}),
        name="notification-bulk-delete",
    ),
]

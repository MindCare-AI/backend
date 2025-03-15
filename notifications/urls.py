# notifications/urls.py
from django.urls import path
from .views import NotificationViewSet

urlpatterns = [
    path("", NotificationViewSet.as_view({"get": "list"}), name="notification-list"),
    path(
        "<int:pk>/",
        NotificationViewSet.as_view({"get": "retrieve"}),
        name="notification-detail",
    ),
    path(
        "<int:pk>/mark_read/",
        NotificationViewSet.as_view({"patch": "mark_read"}),
        name="mark-read",
    ),
    path(
        "mark_all_read/",
        NotificationViewSet.as_view({"post": "mark_all_read"}),
        name="mark-all-read",
    ),
    path(
        "unread_count/",
        NotificationViewSet.as_view({"get": "unread_count"}),
        name="unread-count",
    ),
]

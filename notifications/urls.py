# notifications/urls.py
from django.urls import path
from .views import NotificationViewSet

urlpatterns = [
    path("", NotificationViewSet.as_view({"get": "list"}), name="notification-list"),
    path(
        "<uuid:pk>/",
        NotificationViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="notification-detail",
    ),
    path(
        "mark-all-read/",
        NotificationViewSet.as_view({"post": "mark_all_read"}),
        name="mark-all-read",
    ),
]

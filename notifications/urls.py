# notifications/urls.py
from django.urls import path
from .views import (
    NotificationListView,
    MarkNotificationReadView,
    NotificationBulkActionView,
    NotificationPreferencesView,
    NotificationCountView,
    MarkAllNotificationsReadView,
    notifications_list,
    activate,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("count/", NotificationCountView.as_view(), name="count"),
    path("bulk-action/", NotificationBulkActionView.as_view(), name="bulk-action"),
    path("preferences/", NotificationPreferencesView.as_view(), name="preferences"),
    path("category/<str:category>/", notifications_list, name="category-list"),
    path("<int:pk>/mark-read/", MarkNotificationReadView.as_view(), name="mark-read"),
    path(
        "mark-all-read/", MarkAllNotificationsReadView.as_view(), name="mark-all-read"
    ),
    path("activate/<uidb64>/<token>/", activate, name="activate"),
]

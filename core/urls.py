from django.urls import path, include

urlpatterns = [
    path("auth/", include("auth.urls")),
    path("users/", include("users.urls")),
    path("mood/", include("mood.urls")),
    path("journal/", include("journal.urls")),
    path("therapy/", include("therapy.urls")),
    path("community/", include("community.urls")),
    path("activities/", include("activities.urls")),
    path("notifications/", include("notifications.urls")),
    path("analytics/", include("analytics.urls")),
]

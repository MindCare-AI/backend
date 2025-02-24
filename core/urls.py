#core/urls.py
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="red"),
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
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

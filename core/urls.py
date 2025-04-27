# core/urls.py
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
    path('users/', include('users.urls')),
    path('journal/', include('journal.urls')),
    path('mood/', include('mood.urls')),
    path('feeds/', include('feeds.urls')),
    path('media/', include('media_handler.urls')),
    path('messaging/', include('messaging.urls')),
    path('appointments/', include('appointments.urls')),
    path('patient/', include('patient.urls')),
    path('therapist/', include('therapist.urls')),
    path('notifications/', include('notifications.urls')),
    path('ai/', include('AI_engine.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

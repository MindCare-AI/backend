# users\urls.py
from django.urls import path
from .views import (
    CustomUserViewSet,
    UserPreferencesViewSet,
    UserSettingsViewSet,
)

urlpatterns = [
    # User Endpoints
    path("", CustomUserViewSet.as_view({"get": "list"}), name="user-list"),
    path(
        "<int:pk>/", CustomUserViewSet.as_view({"get": "retrieve"}), name="user-detail"
    ),
    # Preferences & Settings
    path(
        "preferences/",
        UserPreferencesViewSet.as_view({"get": "list"}),
        name="preferences-list",
    ),
    path(
        "preferences/<int:pk>/",
        UserPreferencesViewSet.as_view({"get": "retrieve", "put": "update"}),
        name="preferences-detail",
    ),
    path(
        "settings/", UserSettingsViewSet.as_view({"get": "list"}), name="settings-list"
    ),
    path(
        "settings/<int:pk>/",
        UserSettingsViewSet.as_view({"get": "retrieve", "put": "update"}),
        name="settings-detail",
    ),
]

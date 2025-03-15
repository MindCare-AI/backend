# users\urls.py
from django.urls import path
from .views import (
    CustomUserViewSet,
    UserPreferencesViewSet,
    UserSettingsViewSet,
    SetUserTypeView,
)

urlpatterns = [
    # User Endpoints
    path("", CustomUserViewSet.as_view({"get": "list"}), name="user-list"),
    path(
        "<int:pk>/", CustomUserViewSet.as_view({"get": "retrieve"}), name="user-detail"
    ),
    # Custom action for updating preferences
    path(
        "<int:pk>/update_preferences/",
        CustomUserViewSet.as_view({"patch": "update_preferences"}),
        name="user-update-preferences",
    ),
    # Preferences Endpoints
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
    # Settings Endpoints
    path(
        "settings/",
        UserSettingsViewSet.as_view({"get": "list"}),
        name="settings-list",
    ),
    path(
        "settings/<int:pk>/",
        UserSettingsViewSet.as_view({"get": "retrieve", "put": "update"}),
        name="settings-detail",
    ),
    # Set User Type Endpoint
    path("set-user-type/", SetUserTypeView.as_view(), name="set-user-type"),
]

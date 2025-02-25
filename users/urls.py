# users\urls.py
from django.urls import path
from .views import (
    UserProfileViewSet,
    UserPreferencesViewSet,
    UserSettingsViewSet,
    UserListView  # Added import
)

urlpatterns = [
    path(
        "profiles/",
        UserProfileViewSet.as_view({"get": "list", "post": "create"}),
        name="profile-list",
    ),
    path(
        "profiles/<int:pk>/",
        UserProfileViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="profile-detail",
    ),
    path(
        "preferences/",
        UserPreferencesViewSet.as_view({"get": "list", "post": "create"}),
        name="preferences-list",
    ),
    path(
        "preferences/<int:pk>/",
        UserPreferencesViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="preferences-detail",
    ),
    path(
        "settings/",
        UserSettingsViewSet.as_view({"get": "list", "post": "create"}),
        name="settings-list",
    ),
    path(
        "settings/<int:pk>/",
        UserSettingsViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="settings-detail",
    ),
    path("users/", UserListView.as_view(), name="user-list"),  # Added UserListView
]

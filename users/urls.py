# users\urls.py
from django.urls import path
from users.views.preferences_views import UserPreferencesViewSet
from users.views.settings_views import UserSettingsViewSet
from users.views.user_views import CustomUserViewSet, SetUserTypeView, me, UserViewSet

urlpatterns = [
    path("", CustomUserViewSet.as_view({"get": "list"}), name="user-list"),
    path(
        "<int:pk>/", CustomUserViewSet.as_view({"get": "retrieve"}), name="user-detail"
    ),
    path(
        "<int:pk>/update_preferences/",
        CustomUserViewSet.as_view({"patch": "update_preferences"}),
        name="user-update-preferences",
    ),
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
        "settings/",
        UserSettingsViewSet.as_view(
            {
                "get": "list",
                "post": "create",
                "put": "update",
                "patch": "partial_update",
            }
        ),
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
    path(
        "set-user-type/",
        SetUserTypeView.as_view({"post": "create", "get": "list"}),
        name="set-user-type",
    ),
    path("search/", UserViewSet.as_view({"get": "search"}), name="user-search"),
    path("me/", me, name="user-me"),
    path('list-all/', CustomUserViewSet.as_view({'get': 'list_all_users'}), name='user-list-all'),
]

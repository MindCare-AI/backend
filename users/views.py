# users/views.py
from rest_framework import viewsets, permissions
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import UserProfile, UserPreferences, UserSettings
from .serializers import (
    UserProfileSerializer,
    UserPreferencesSerializer,
    UserDetailSerializer,
    UserSettingsSerializer,
)

CustomUser = get_user_model()


class IsSuperUserOrSelf(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Allow superusers full access
        if request.user.is_superuser:
            return True
        # Allow users to access their own data
        return obj.user == request.user


@extend_schema_view(
    list=extend_schema(
        description="Get user profile information. Returns user's own profile for regular users.",
        summary="Get User Profile",
        tags=["Profile"],
    ),
    update=extend_schema(
        description="Update user profile information (bio, timezone, etc.)",
        summary="Update Profile",
        tags=["Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update profile information",
        summary="Patch Profile",
        tags=["Profile"],
    ),
)
class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        if self.request.user.is_superuser:
            return UserProfile.objects.select_related("user").all()
        return UserProfile.objects.select_related("user").filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description="Get user preferences including language and notification settings",
        summary="Get User Preferences",
        tags=["Preferences"],
    ),
    update=extend_schema(
        description="Update user preferences",
        summary="Update Preferences",
        tags=["Preferences"],
    ),
    partial_update=extend_schema(
        description="Partially update user preferences",
        summary="Patch Preferences",
        tags=["Preferences"],
    ),
)
class UserPreferencesViewSet(viewsets.ModelViewSet):
    serializer_class = UserPreferencesSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return UserPreferences.objects.all()
        return UserPreferences.objects.filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description="Get user settings including theme and notification configurations",
        summary="Get User Settings",
        tags=["Settings"],
    ),
    update=extend_schema(
        description="Update user settings", summary="Update Settings", tags=["Settings"]
    ),
    partial_update=extend_schema(
        description="Partially update user settings",
        summary="Patch Settings",
        tags=["Settings"],
    ),
)
class UserSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return UserSettings.objects.all()
        return UserSettings.objects.filter(user=self.request.user)


class UserListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema(
    description="Get authenticated user's full profile with related data",
    summary="Get User Details",
    tags=["User"],
    parameters=[
        {
            "name": "page_size",
            "type": "integer",
            "description": "Number of results per page",
            "required": False,
            "in": "query",
        }
    ],
)
class UserListView(ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = UserListPagination

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomUser.objects.all()
        return CustomUser.objects.filter(id=self.request.user.id)

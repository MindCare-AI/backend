# users/views/user_views.py
from rest_framework import viewsets, status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.apps import apps
from users.models.user import CustomUser
from users.models.settings import UserSettings

from ..models.preferences import UserPreferences
from ..permissions.user import IsSuperUserOrSelf
from ..serializers.user import (
    CustomUserSerializer,
    UserPreferencesSerializer,
    UserSettingsSerializer,
    UserSerializer,
    UserTypeSerializer,
    UserRegistrationSerializer,
)

from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer

import logging

logger = logging.getLogger(__name__)


def get_therapist_profile():
    return apps.get_model("therapist", "TherapistProfile")


TherapistProfile = apps.get_model("therapist", "TherapistProfile")


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
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = UserListPagination

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomUser.objects.all()
        return CustomUser.objects.filter(id=self.request.user.id)


@extend_schema_view(
    list=extend_schema(
        description="Get user information",
        summary="Get Users",
        tags=["User"],
    ),
    retrieve=extend_schema(
        description="Get specific user details",
        summary="Get User",
        tags=["User"],
    ),
)
class CustomUserViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({"message": "List of users"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"Detail of user {pk}"})

    def update_preferences(self, request, pk=None):
        return Response({"message": f"Update preferences for user {pk}"})


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperUserOrSelf]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return CustomUser.objects.all().prefetch_related("preferences", "settings")
        return CustomUser.objects.filter(id=user.id).prefetch_related(
            "preferences", "settings"
        )

    @action(detail=True, methods=["patch"])
    def update_preferences(self, request, pk=None):
        try:
            user = self.get_object()
            preferences, created = UserPreferences.objects.get_or_create(user=user)

            serializer = UserPreferencesSerializer(
                preferences, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        "message": "Preferences updated successfully",
                        "preferences": serializer.data,
                    }
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["patch"])
    def update_settings(self, request, pk=None):
        try:
            user = self.get_object()
            settings, created = UserSettings.objects.get_or_create(user=user)

            serializer = UserSettingsSerializer(
                settings, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        "message": "Settings updated successfully",
                        "settings": serializer.data,
                    }
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update settings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def set_user_type(self, request):
        user = request.user
        serializer = UserTypeSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User type updated successfully"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SetUserTypeView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]  # Changed from CanSetUserType

    def list(self, request):
        user_type_choices = {
            choice[0]: choice[1] for choice in CustomUser.USER_TYPE_CHOICES
        }
        return Response(
            {
                "available_user_types": user_type_choices,
                "current_user_type": request.user.user_type,
                "message": "Use POST to set your user type",
            }
        )

    def create(self, request):
        user = request.user
        # Add a check to prevent changing user_type if already set
        if user.user_type and not user.is_superuser:
            return Response(
                {"error": "User type can only be set once"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserTypeSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User type updated successfully"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Register a new user account",
    summary="Register User",
    tags=["Authentication"],
    request=UserRegistrationSerializer,
    responses={
        201: {"description": "User successfully registered"},
        400: {"description": "Invalid input data"},
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer, BrowsableAPIRenderer])  # Add format support
def register_user(request, format=None):
    """
    Register a new user with email, password, and optional profile information.

    Supported formats:
    - JSON (default)
    - Browsable API (HTML)
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                "message": "User registered successfully",
                "user": {"id": user.id, "email": user.email, "username": user.username},
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Get Current User Profile",
    description=(
        "Retrieve the full profile of the currently authenticated user. "
        "This includes details such as the user's type, preferences, settings, "
        "and associated profiles (patient/therapist)."
    ),
    responses={200: UserSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Retrieve current user's full information including user type.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

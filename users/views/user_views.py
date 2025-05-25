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
    UserListSerializer,  # Add this import
)

from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

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
    permission_classes = [IsAuthenticated]  # Add permission class

    def list(self, request):
        return Response({"message": "List of users"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"Detail of user {pk}"})

    def update_preferences(self, request, pk=None):
        return Response({"message": f"Update preferences for user {pk}"})

    @extend_schema(
        description="List all users with basic information",
        summary="List All Users",
        tags=["User"],
        responses={200: UserListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="list-all")
    def list_all_users(self, request):
        """Get a list of all users with basic information."""
        try:
            users = CustomUser.objects.all().order_by("username")
            serializer = UserListSerializer(users, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching user list: {str(e)}")
            return Response(
                {"error": "Failed to fetch user list"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @extend_schema(
        summary="Search Users",
        description="Search for users by username, email, first name, or last name",
        parameters=[
            OpenApiParameter(
                name="q",
                description="Search query (username, email, first/last name)",
                required=True,
                type=OpenApiTypes.STR,
            ),
            OpenApiParameter(
                name="user_type",
                description="Filter by user type (patient, therapist)",
                required=False,
                type=OpenApiTypes.STR,
                enum=["patient", "therapist"],
            ),
        ],
        responses={
            200: CustomUserSerializer(many=True)
        },  # Change to simpler serializer
    )
    @action(detail=False, methods=["get"])
    def search(self, request):
        """
        Search for users by name, email, or username.
        """
        try:
            query = request.query_params.get("q", "")
            user_type = request.query_params.get("user_type", None)

            if not query:
                return Response(
                    {"error": "Search query is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = CustomUser.objects.filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )

            if user_type:
                queryset = queryset.filter(user_type=user_type)

            # Limit results for performance
            queryset = queryset[:20]

            # Use a simpler serializer to avoid potential relation issues
            serializer = CustomUserSerializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in user search: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred during search: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SetUserTypeView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

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

        # Check if user_type is already set (optional: remove if you want to allow changes)
        if user.user_type and not user.is_superuser:
            return Response(
                {"error": "User type can only be set once"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Import the updated serializer
        from ..serializers.user import UserTypeSerializer

        serializer = UserTypeSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(
                    {
                        "message": "User type updated successfully",
                        "user_type": user.user_type,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.error(f"Error setting user type: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Failed to set user type: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

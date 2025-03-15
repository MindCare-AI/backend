# users/views.py
from rest_framework import viewsets, permissions, status, generics
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.views import APIView
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .models import (
    UserPreferences,
    UserSettings,
    PatientProfile,
    TherapistProfile,
    CustomUser,
)
from .permissions import IsSuperUserOrSelf
from .serializers import (
    CustomUserSerializer,
    UserPreferencesSerializer,
    UserSettingsSerializer,
    PatientProfileSerializer,
    TherapistProfileSerializer,
    UserTypeSerializer,
    UserSerializer,
)
import logging

logger = logging.getLogger(__name__)

CustomUser = get_user_model()


@extend_schema_view(
    retrieve=extend_schema(
        description="Get user preferences",
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
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Get or create preferences for current user"""
        preferences, created = UserPreferences.objects.get_or_create(
            user=self.request.user
        )
        return preferences

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        """Update preferences with error handling"""
        try:
            instance = serializer.save()
            logger.info(f"Updated preferences for user {self.request.user.id}")
            return instance
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}")
            raise


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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return UserSettings.objects.all()
        return UserSettings.objects.filter(user=self.request.user)

    def get_object(self):
        """Get or create UserSettings for the current user."""
        user = self.request.user
        settings_obj, created = UserSettings.objects.get_or_create(user=user)
        return settings_obj

    def update(self, request, *args, **kwargs):
        """
        Update user settings.
        Ensure that the payload uses the correct field name ('user_timezone' instead of 'timezone').
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


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
class CustomUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = UserListPagination

    def get_queryset(self):
        if self.request.user.is_superuser:
            return (
                CustomUser.objects.all()
                .select_related("preferences", "settings")
                .prefetch_related("therapist_appointments", "patient_appointments")
            )
        return CustomUser.objects.filter(id=self.request.user.id).select_related(
            "preferences", "settings"
        )

    @extend_schema(
        description="Update user preferences",
        summary="Update User Preferences",
        tags=["User"],
    )
    @action(detail=True, methods=["patch"])
    def update_preferences(self, request, pk=None):
        """Update user preferences with validation"""
        try:
            user = self.get_object()
            preferences, created = UserPreferences.objects.get_or_create(
                user=user,
                defaults={
                    "dark_mode": False,
                    "language": settings.LANGUAGE_CODE,
                    "notification_preferences": {},
                },
            )

            serializer = UserPreferencesSerializer(
                preferences, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                logger.info(f"Updated preferences for user {user.username}")
                return Response(
                    {
                        "message": "Preferences updated successfully",
                        "preferences": serializer.data,
                    }
                )

            logger.warning(
                f"Invalid preference data for user {user.username}: {serializer.errors}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except CustomUser.DoesNotExist:
            logger.error(f"User {pk} not found")
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Update user settings",
        summary="Update User Settings",
        tags=["User"],
    )
    @action(detail=True, methods=["patch"])
    def update_settings(self, request, pk=None):
        """Update user settings with validation"""
        try:
            user = self.get_object()
            settings, created = UserSettings.objects.get_or_create(
                user=user,
                defaults={
                    "timezone": settings.TIME_ZONE,
                    "theme_preferences": {"mode": "system"},
                    "privacy_settings": {"profile_visibility": "public"},
                },
            )

            serializer = UserSettingsSerializer(
                settings, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                logger.info(f"Updated settings for user {user.username}")
                return Response(
                    {
                        "message": "Settings updated successfully",
                        "settings": serializer.data,
                    }
                )

            logger.warning(
                f"Invalid settings data for user {user.username}: {serializer.errors}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except CustomUser.DoesNotExist:
            logger.error(f"User {pk} not found")
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update settings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    list=extend_schema(
        description="Get patient profile information",
        summary="Get Patient Profile",
        tags=["Profile"],
    ),
    update=extend_schema(
        description="Update patient profile information",
        summary="Update Patient Profile",
        tags=["Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update profile information",
        summary="Patch Profile",
        tags=["Profile"],
    ),
)
class PatientProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "put", "patch", "delete"]  # Remove POST method

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PatientProfile.objects.select_related("user").all()
        return PatientProfile.objects.select_related("user").filter(
            user=self.request.user
        )


@extend_schema_view(
    list=extend_schema(
        description="Get therapist profile information",
        summary="Get Therapist Profile",
        tags=["Profile"],
    ),
    update=extend_schema(
        description="Update therapist profile information",
        summary="Update Therapist Profile",
        tags=["Profile"],
    ),
)
class TherapistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "put", "patch", "delete"]  # Remove POST method

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TherapistProfile.objects.select_related("user").all()
        return TherapistProfile.objects.select_related("user").filter(
            user=self.request.user
        )


class BecomePatientView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserTypeSerializer(
            request.user, data={"user_type": "patient"}, partial=True
        )

        if serializer.is_valid():
            user = serializer.save()
            PatientProfile.objects.create(user=user)
            return Response(
                {"detail": "Successfully became a patient"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BecomeTherapistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserTypeSerializer(
            request.user, data={"user_type": "therapist"}, partial=True
        )

        if serializer.is_valid():
            user = serializer.save()
            TherapistProfile.objects.create(user=user)
            return Response(
                {"detail": "Successfully became a therapist"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserTypeView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    http_method_names = ["patch"]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        new_type = request.data.get("user_type")

        # Replace USER_TYPES with USER_TYPE_CHOICES
        if new_type not in [choice[0] for choice in CustomUser.USER_TYPE_CHOICES]:
            return Response(
                {
                    "error": f"Invalid user type. Must be one of: {', '.join([choice[0] for choice in CustomUser.USER_TYPE_CHOICES])}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if the user is already the requested type
        if user.user_type == new_type:
            return Response(
                {"message": f"User is already a {new_type}"}, status=status.HTTP_200_OK
            )

        try:
            with transaction.atomic():
                # Update the user type
                user.user_type = new_type
                user.save()

                # Create the corresponding profile if it doesn't exist
                if new_type == "patient":
                    PatientProfile.objects.get_or_create(user=user)
                elif new_type == "therapist":
                    TherapistProfile.objects.get_or_create(user=user)

                logger.info(f"User {user.username} changed type to {new_type}")

                serializer = self.get_serializer(user)
                return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error changing user type: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not change user type. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperUserOrSelf]

    def get_queryset(self):
        """
        Return all users for admin,
        or just the user themselves for regular users.
        """
        user = self.request.user
        if user.is_superuser:
            return CustomUser.objects.all().prefetch_related("preferences", "settings")
        return CustomUser.objects.filter(id=user.id).prefetch_related(
            "preferences", "settings"
        )

    @action(detail=True, methods=["patch"])
    def update_preferences(self, request, pk=None):
        """
        Update user preferences
        """
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
        """
        Update user settings
        """
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


class SetUserTypeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserTypeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            request.user, data=request.data, partial=True
        )

        try:
            if serializer.is_valid():
                user = serializer.save()

                # Generate new tokens with updated claims
                refresh = RefreshToken.for_user(user)
                refresh["user_type"] = user.user_type

                logger.info(f"User {user.username} type updated to {user.user_type}")

                return Response(
                    {
                        "message": "User type updated successfully",
                        "user_type": user.user_type,
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    }
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in SetUserTypeView: {str(e)}")
            return Response(
                {"error": "Could not update user type"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

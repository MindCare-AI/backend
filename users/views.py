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
from .models import UserPreferences, UserSettings, PatientProfile, TherapistProfile, CustomUser
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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def toggle_dark_mode(self, request, pk=None):
        preferences = self.get_object()
        preferences.dark_mode = not preferences.dark_mode
        preferences.save()
        return Response({"dark_mode": preferences.dark_mode}, status=status.HTTP_200_OK)


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
            return CustomUser.objects.all()
        return CustomUser.objects.filter(id=self.request.user.id)


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
            request.user,
            data={'user_type': 'patient'},
            partial=True
        )
        
        if serializer.is_valid():
            user = serializer.save()
            PatientProfile.objects.create(user=user)
            return Response(
                {'detail': 'Successfully became a patient'}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BecomeTherapistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserTypeSerializer(
            request.user,
            data={'user_type': 'therapist'},
            partial=True
        )
        
        if serializer.is_valid():
            user = serializer.save()
            TherapistProfile.objects.create(user=user)
            return Response(
                {'detail': 'Successfully became a therapist'}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserTypeView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        user = self.get_object()
        new_type = request.data.get('user_type')
        
        # Validate the new type
        if new_type not in [choice[0] for choice in CustomUser.USER_TYPES]:
            return Response(
                {"error": f"Invalid user type. Must be one of: {', '.join([choice[0] for choice in CustomUser.USER_TYPES])}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if the user is already the requested type
        if user.user_type == new_type:
            return Response(
                {"message": f"User is already a {new_type}"},
                status=status.HTTP_200_OK
            )
            
        try:
            with transaction.atomic():
                # Update the user type
                user.user_type = new_type
                user.save()
                
                # Create the corresponding profile if it doesn't exist
                if new_type == 'patient':
                    PatientProfile.objects.get_or_create(user=user)
                elif new_type == 'therapist':
                    TherapistProfile.objects.get_or_create(user=user)
                    
                logger.info(f"User {user.username} changed type to {new_type}")
                
                serializer = self.get_serializer(user)
                return Response(serializer.data)
                
        except Exception as e:
            logger.error(f"Error changing user type: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not change user type. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            return CustomUser.objects.all().prefetch_related('preferences', 'settings')
        return CustomUser.objects.filter(id=user.id).prefetch_related('preferences', 'settings')
    
    @action(detail=True, methods=['patch'])
    def update_preferences(self, request, pk=None):
        """
        Update user preferences
        """
        try:
            user = self.get_object()
            preferences = user.preferences
            
            for field, value in request.data.items():
                if hasattr(preferences, field):
                    setattr(preferences, field, value)
            
            preferences.save()
            
            return Response({
                "message": "Preferences updated successfully",
                "preferences": UserPreferences.objects.get(user=user)
            })
            
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update preferences. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['patch'])
    def update_settings(self, request, pk=None):
        """
        Update user settings
        """
        try:
            user = self.get_object()
            settings = user.settings
            
            for field, value in request.data.items():
                if hasattr(settings, field):
                    setattr(settings, field, value)
            
            settings.save()
            
            return Response({
                "message": "Settings updated successfully",
                "settings": UserSettings.objects.get(user=user)
            })
            
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update settings. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SetUserTypeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        user_type = request.data.get('user_type')
        
        if not user_type:
            return Response(
                {"error": "User type is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if user_type not in ['patient', 'therapist']:
            return Response(
                {"error": "Invalid user type. Must be 'patient' or 'therapist'"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Don't allow changing user_type if already set
        if user.user_type:
            return Response(
                {"error": "User type is already set"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user.user_type = user_type
        user.save()
        
        # Create appropriate profile
        try:
            if user_type == "patient":
                profile, created = PatientProfile.objects.get_or_create(
                    user=user,
                    defaults={"profile_type": "patient"}
                )
            elif user_type == "therapist":
                profile, created = TherapistProfile.objects.get_or_create(
                    user=user,
                    defaults={"profile_type": "therapist"}
                )
                
            return Response({
                "message": f"User type set to {user_type}",
                "profile_id": profile.id,
                "created": created
            })
                
        except Exception as e:
            return Response(
                {"error": f"Error creating profile: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

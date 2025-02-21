# Create your views here.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import CustomUser, AuthToken, UserDevice, UserProfile, UserPreferences, UserSettings
from .serializers import (
    CustomUserSerializer,
    AuthTokenSerializer,
    UserDeviceSerializer,
    UserProfileSerializer,
    UserPreferencesSerializer,
    UserSettingsSerializer
)

# CustomUser ViewSet
class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Custom logic for user creation (e.g., password hashing)
        return super().create(request, *args, **kwargs)

# AuthToken ViewSet
class AuthTokenViewSet(viewsets.ModelViewSet):
    queryset = AuthToken.objects.all()
    serializer_class = AuthTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Custom logic to create AuthTokens, e.g., generate tokens
        return super().create(request, *args, **kwargs)

# UserDevice ViewSet
class UserDeviceViewSet(viewsets.ModelViewSet):
    queryset = UserDevice.objects.all()
    serializer_class = UserDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

# UserProfile ViewSet
class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

# UserPreferences ViewSet
class UserPreferencesViewSet(viewsets.ModelViewSet):
    queryset = UserPreferences.objects.all()
    serializer_class = UserPreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]

# UserSettings ViewSet
class UserSettingsViewSet(viewsets.ModelViewSet):
    queryset = UserSettings.objects.all()
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

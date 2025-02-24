#users\views.py
from rest_framework import viewsets, permissions
from .models import UserProfile, UserPreferences, UserSettings
from .serializers import (
    UserProfileSerializer,
    UserPreferencesSerializer,
    UserSettingsSerializer,
)

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

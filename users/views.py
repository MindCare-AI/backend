from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import UserProfile, UserPreferences, UserSettings
from .serializers import (
    UserProfileSerializer,
    UserPreferencesSerializer,
    UserSettingsSerializer,
    UserDetailSerializer,
)

CustomUser = get_user_model()

# Fix the UserProfileViewSet - it was incorrectly set up
class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

# Add the missing UserPreferencesViewSet
class UserPreferencesViewSet(viewsets.ModelViewSet):
    queryset = UserPreferences.objects.all()
    serializer_class = UserPreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]

class UserSettingsViewSet(viewsets.ModelViewSet):
    queryset = UserSettings.objects.all()
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

# Add a view to list all users with their details
class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        users = CustomUser.objects.all()
        serializer = UserDetailSerializer(users, many=True)
        return Response(serializer.data)

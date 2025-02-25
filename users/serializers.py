from rest_framework import serializers
from .models import CustomUser, UserProfile, UserPreferences, UserSettings
from django.contrib.auth import get_user_model

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "user", "bio", "profile_pic", "timezone", "privacy_settings"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["id", "user", "notification_settings", "language", "accessibility"]


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["id", "user", "theme", "display_preferences", "privacy_level"]


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for users that includes all related information
    from profile, preferences, and settings models.
    """
    profile = UserProfileSerializer(read_only=True)
    preferences = UserPreferencesSerializer(read_only=True)
    settings = UserSettingsSerializer(read_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'created_at', 'profile',
            'preferences', 'settings'
        ]

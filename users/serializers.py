from rest_framework import serializers
from .models import CustomUser, UserProfile, UserPreferences, UserSettings
from django.contrib.auth import get_user_model

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'created_at', 'date_joined']

class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_pic = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = UserProfile
        fields = [
            "id", 
            "user", 
            "bio", 
            "profile_pic", 
            "timezone", 
            "privacy_settings", 
            "stress_level", 
            "wearable_data", 
            "therapy_preferences"
        ]

    def validate_profile_pic(self, value):
        if value:
            # Add validation for file size if needed
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError("Image file too large ( > 5MB )")
        return value

class UserPreferencesSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = UserPreferences
        fields = [
            "id",
            "user",
            "language",
            "notification_settings",
            "theme",  # Changed from theme_preference
            "accessibility_settings"
        ]

class UserSettingsSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = UserSettings
        fields = [
            "id",
            "user",
            "theme",
            "privacy_level",
            "notifications"  # Single JSON field for all notification settings
        ]

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

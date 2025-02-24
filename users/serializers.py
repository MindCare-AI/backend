from rest_framework import serializers
from .models import UserProfile, UserPreferences, UserSettings

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

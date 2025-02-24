#users\serializers.py
from rest_framework import serializers
from .models import UserProfile, UserPreferences, UserSettings

# Serializer for UserProfile
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "user", "bio", "profile_pic", "timezone", "privacy_settings"]

# Serializer for UserPreferences
class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["id", "user", "notification_settings", "language", "accessibility"]

# Serializer for UserSettings
class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["id", "user", "theme", "display_preferences", "privacy_level"]

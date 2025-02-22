from rest_framework import serializers
from .models import (
    CustomUser,
    AuthToken,
    UserDevice,
    UserProfile,
    UserPreferences,
    UserSettings,
)


# CustomUser serializer
class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email", "username", "password", "is_active", "created_at"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = CustomUser(**validated_data)
        user.set_password(validated_data["password"])  # Hash password
        user.save()
        return user


# AuthToken serializer
class AuthTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthToken
        fields = [
            "id",
            "user",
            "device_id",
            "access_token",
            "refresh_token",
            "created_at",
        ]


# UserDevice serializer
class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ["id", "user", "device_type", "device_id", "last_login"]


# UserProfile serializer
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "user", "bio", "profile_pic", "timezone", "privacy_settings"]


# UserPreferences serializer
class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["id", "user", "notification_settings", "language", "accessibility"]


# UserSettings serializer
class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["id", "user", "theme", "display_preferences", "privacy_level"]

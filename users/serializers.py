# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from .models import UserPreferences, UserSettings
from patient.models import PatientProfile
from therapist.models import TherapistProfile
from patient.serializers import PatientProfileSerializer
from therapist.serializers import TherapistProfileSerializer
import logging

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "created_at",
            "date_joined",
            "user_type"
        ]
        read_only_fields = ["user_type"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["id", "user", "dark_mode", "notification_preferences"]


class UserSettingsSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserSettings
        fields = [
            "id",
            "user",
            "theme",
            "privacy_level",
            "notifications",  # Single JSON field for all notification settings
        ]


class PatientProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "user",
            "bio",
            "profile_pic",
            "timezone",
            "stress_level",
            "wearable_data",
            "therapy_preferences",
        ]

    def validate_profile_pic(self, value):
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Image file too large ( > 5MB )")
        return value


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "bio",
            "profile_pic",
            "specialization",
            "license_number",
            "years_of_experience",
            "availability",
        ]

    def validate_profile_pic(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image file too large ( > 5MB )")
        return value


class UserTypeSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(
        choices=['patient', 'therapist'],
        required=True
    )

    def validate_user_type(self, value):
        user = self.context['request'].user
        if user.user_type and user.user_type != value:
            raise ValidationError("User type cannot be changed once set")
        return value

    def update(self, instance, validated_data):
        instance.user_type = validated_data['user_type']
        # Create corresponding profile
        if validated_data['user_type'] == 'patient':
            PatientProfile.objects.get_or_create(user=instance)
        elif validated_data['user_type'] == 'therapist':
            TherapistProfile.objects.get_or_create(user=instance)
        instance.save()
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    preferences = UserPreferencesSerializer(read_only=True)
    settings = UserSettingsSerializer(read_only=True)
    user_type = serializers.CharField(read_only=True)
    has_profile = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "is_active",
            "date_joined",
            "created_at",
            "profile",
            "preferences",
            "settings",
            "has_profile"
        ]

    def get_has_profile(self, obj):
        """Check if user has created their profile"""
        try:
            if obj.user_type == "patient":
                return hasattr(obj, 'patient_profile')
            elif obj.user_type == "therapist":
                return hasattr(obj, 'therapist_profile')
            return False
        except Exception as e:
            logger.error(f"Error checking profile for user {obj.username}: {str(e)}")
            return False

    def get_profile(self, obj):
        """
        Get user profile based on user type using related names.
        Returns None if profile doesn't exist.
        """
        try:
            if not obj.user_type:
                return None
                
            if obj.user_type == "patient" and hasattr(obj, 'patient_profile'):
                return PatientProfileSerializer(obj.patient_profile).data
            elif obj.user_type == "therapist" and hasattr(obj, 'therapist_profile'):
                return TherapistProfileSerializer(obj.therapist_profile).data
            
            return None
        except Exception as e:
            logger.error(f"Error getting profile for user {obj.username}: {str(e)}")
            return None

# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserPreferences, UserSettings
from patient.models import PatientProfile
from therapist.models import TherapistProfile
from patient.serializers import PatientProfileSerializer
import logging
from django.db import transaction
from utils.validators import (
    validate_emergency_contact,
    validate_blood_type,
    validate_profile_pic,
)
from django.conf import settings
import pytz

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
            "user_type",
        ]
        read_only_fields = ["user_type"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["dark_mode", "language", "notification_preferences"]
        read_only_fields = ["user"]


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "timezone",
            "theme_preferences",
            "privacy_settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserSettingsSerializer(serializers.ModelSerializer):
    timezone = serializers.CharField(
        max_length=50,
        required=False,
        default=settings.TIME_ZONE,
        help_text="User's preferred timezone (e.g., 'UTC', 'America/New_York')",
    )
    theme_preferences = serializers.DictField(
        required=False,
        default=dict,
        help_text="User's theme preferences including mode and color scheme",
    )
    privacy_settings = serializers.DictField(
        required=False,
        default=dict,
        help_text="User's privacy configuration including visibility and status",
    )

    class Meta:
        model = UserSettings
        fields = [
            "id",
            "timezone",
            "theme_preferences",
            "privacy_settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_timezone(self, value):
        """Validate timezone string"""
        try:
            if value not in pytz.all_timezones:
                raise serializers.ValidationError(
                    f"Invalid timezone. Must be one of: {', '.join(pytz.common_timezones)}"
                )
            return value
        except Exception as e:
            logger.error(f"Timezone validation error: {str(e)}")
            raise serializers.ValidationError("Invalid timezone format")

    def validate_theme_preferences(self, value):
        """Validate theme preferences structure and values"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Theme preferences must be an object")

        required_keys = {"mode", "color_scheme"}
        missing_keys = required_keys - set(value.keys())
        if missing_keys:
            raise serializers.ValidationError(
                f"Missing required theme preferences: {', '.join(missing_keys)}"
            )

        valid_modes = settings.USER_SETTINGS["THEME_MODES"]
        if value["mode"] not in valid_modes:
            raise serializers.ValidationError(
                f"Invalid theme mode. Must be one of: {', '.join(valid_modes)}"
            )

        return value

    def validate_privacy_settings(self, value):
        """Validate privacy settings structure and values"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Privacy settings must be an object")

        required_keys = {"profile_visibility", "show_online_status"}
        missing_keys = required_keys - set(value.keys())
        if missing_keys:
            raise serializers.ValidationError(
                f"Missing required privacy settings: {', '.join(missing_keys)}"
            )

        valid_visibilities = settings.USER_SETTINGS["PRIVACY_LEVELS"]
        if value["profile_visibility"] not in valid_visibilities:
            raise serializers.ValidationError(
                f"Invalid visibility level. Must be one of: {', '.join(valid_visibilities)}"
            )

        if not isinstance(value["show_online_status"], bool):
            raise serializers.ValidationError("show_online_status must be a boolean")

        return value

    def validate_pain_level(self, value):
        """Validate pain level is within range"""
        try:
            pain_level = int(value)
            if not (0 <= pain_level <= 10):
                raise serializers.ValidationError("Pain level must be between 0 and 10")
            return pain_level
        except (TypeError, ValueError):
            raise serializers.ValidationError("Pain level must be a number")

    def to_representation(self, instance):
        """Add default values to response"""
        data = super().to_representation(instance)

        # Add default theme preferences
        if not data.get("theme_preferences"):
            data["theme_preferences"] = settings.USER_SETTINGS["DEFAULT_THEME"]

        # Add default privacy settings
        if not data.get("privacy_settings"):
            data["privacy_settings"] = settings.USER_SETTINGS["DEFAULT_PRIVACY"]

        return data


class PatientProfileSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(
        validators=[validate_profile_pic], required=False
    )
    emergency_contact = serializers.JSONField(
        validators=[validate_emergency_contact], required=False
    )
    blood_type = serializers.CharField(validators=[validate_blood_type], required=False)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "bio",
            "profile_pic",
            "emergency_contact",
            "medical_history",
            "current_medications",
            "blood_type",
            "treatment_plan",
            "pain_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TherapistProfileSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(
        validators=[validate_profile_pic], required=False
    )
    profile_completion_percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "bio",
            "profile_pic",
            "specialization",
            "license_number",
            "years_of_experience",
            "treatment_approaches",
            "consultation_fee",
            "available_days",
            "license_expiry",
            "video_session_link",
            "languages_spoken",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
        ]


class UserTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user type with validation and profile handling
    """

    class Meta:
        model = CustomUser
        fields = ["user_type"]

    def validate_user_type(self, value):
        valid_types = [choice[0] for choice in CustomUser.USER_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid user type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate(self, attrs):
        # Comment out or remove the following check if you want to allow updating user_type
        # if self.instance and self.instance.user_type is not None:
        #     raise serializers.ValidationError(
        #         {"user_type": "User type can only be set once"}
        #     )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        try:
            # Update user type
            instance.user_type = validated_data["user_type"]
            instance.save()

            # Create corresponding profile
            if instance.user_type == "patient" and not hasattr(
                instance, "patient_profile"
            ):
                PatientProfile.objects.create(user=instance)
            elif instance.user_type == "therapist" and not hasattr(
                instance, "therapist_profile"
            ):
                TherapistProfile.objects.create(user=instance)

            return instance
        except Exception as e:
            logger.error(f"Error updating user type: {str(e)}")
            raise serializers.ValidationError({"detail": "Unable to update user type"})


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
            "has_profile",
        ]

    def get_has_profile(self, obj):
        """Check if user has created their profile"""
        try:
            if obj.user_type == "patient":
                return hasattr(obj, "patient_profile")
            elif obj.user_type == "therapist":
                return hasattr(obj, "therapist_profile")
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

            if obj.user_type == "patient" and hasattr(obj, "patient_profile"):
                return PatientProfileSerializer(obj.patient_profile).data
            elif obj.user_type == "therapist" and hasattr(obj, "therapist_profile"):
                return TherapistProfileSerializer(obj.therapist_profile).data

            return None
        except Exception as e:
            logger.error(f"Error getting profile for user {obj.username}: {str(e)}")
            return None


class UserSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(source="patientprofile", read_only=True)
    therapist_profile = TherapistProfileSerializer(
        source="therapistprofile", read_only=True
    )
    preferences = UserPreferencesSerializer(read_only=True)
    settings = UserSettingsSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "user_type",
            "phone_number",
            "date_of_birth",
            "preferences",
            "settings",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

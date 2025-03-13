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
from django.db import transaction
from .models import CustomUser, PatientProfile, TherapistProfile, UserPreferences, UserSettings
from utils.validators import validate_emergency_contact, validate_blood_type, validate_profile_pic

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
        fields = ['language', 'dark_mode', 'notification_email', 'notification_sms', 'notification_app']


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ['timezone', 'two_factor_auth', 'data_sharing']


class PatientProfileSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(validators=[validate_profile_pic], required=False)
    emergency_contact = serializers.JSONField(validators=[validate_emergency_contact], required=False)
    blood_type = serializers.CharField(validators=[validate_blood_type], required=False)

    class Meta:
        model = PatientProfile
        fields = ['id', 'bio', 'profile_pic', 'emergency_contact', 'medical_history', 
                 'current_medications', 'blood_type', 'treatment_plan', 'pain_level',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TherapistProfileSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(validators=[validate_profile_pic], required=False)
    profile_completion_percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = TherapistProfile
        fields = ['id', 'bio', 'profile_pic', 'specialization', 'license_number', 
                 'years_of_experience', 'treatment_approaches', 'consultation_fee',
                 'available_days', 'license_expiry', 'video_session_link',
                 'languages_spoken', 'profile_completion_percentage',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'profile_completion_percentage', 'created_at', 'updated_at']


class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['user_type']

    def validate_user_type(self, value):
        if value not in ['patient', 'therapist']:
            raise serializers.ValidationError("User type must be either 'patient' or 'therapist'")
        return value

    def validate(self, attrs):
        if self.instance and self.instance.user_type is not None:
            raise serializers.ValidationError({
                "user_type": "User type can only be set once"
            })
        return attrs

    def update(self, instance, validated_data):
        try:
            with transaction.atomic():
                instance.user_type = validated_data['user_type']
                instance.save()
                
                # Signal handler will create the profile, but let's verify
                if not hasattr(instance, f"{instance.user_type}_profile"):
                    logger.warning(f"Profile not created for user {instance.username}")
                    
                return instance
                
        except Exception as e:
            logger.error(f"Error updating user type: {str(e)}")
            raise serializers.ValidationError({
                "detail": "Unable to update user type"
            })


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


class UserSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(source='patientprofile', read_only=True)
    therapist_profile = TherapistProfileSerializer(source='therapistprofile', read_only=True)
    preferences = UserPreferencesSerializer(read_only=True)
    settings = UserSettingsSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'user_type', 'date_of_birth', 'phone_number', 
                 'patient_profile', 'therapist_profile',
                 'preferences', 'settings']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

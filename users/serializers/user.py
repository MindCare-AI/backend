# users/serializers/user.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.apps import apps

# Update imports to use app-specific serializers
from patient.serializers.patient_profile import PatientProfileSerializer
from therapist.serializers.therapist_profile import TherapistProfileSerializer
from .preferences import UserPreferencesSerializer
from .settings import UserSettingsSerializer

import logging

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class CustomUserSerializer(serializers.ModelSerializer):
    USER_STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("SUSPENDED", "Suspended"),
        ("PENDING", "Pending Verification"),
    ]

    status = serializers.ChoiceField(
        choices=USER_STATUS_CHOICES,
        default="PENDING",
        help_text="Current status of the user account",
    )

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
            "status",
        ]
        read_only_fields = ["user_type"]


class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["user_type"]

    def validate_user_type(self, value):
        """Validate that user_type is one of the allowed choices"""
        if value not in ["patient", "therapist"]:
            raise serializers.ValidationError(
                "User type must be either 'patient' or 'therapist'"
            )
        return value

    def update(self, instance, validated_data):
        """Handle user type update and create associated profiles"""
        user_type = validated_data.get("user_type")

        # Update the user type
        instance.user_type = user_type
        instance.save()

        # Create associated profile based on user type
        if user_type == "therapist":
            # Get the TherapistProfile model dynamically to avoid import issues
            TherapistProfile = apps.get_model("therapist", "TherapistProfile")

            # Create or get therapist profile with proper defaults that respect constraints
            therapist_profile, created = TherapistProfile.objects.get_or_create(
                user=instance,
                defaults={
                    # Don't set license_number at all - let the model handle the default
                    "bio": "",
                    "years_of_experience": 0,
                    "verification_status": "pending",
                    "specializations": [],
                    "education": [],
                    "experience": [],
                    "available_days": {},
                    "languages": [],
                    "therapy_types": [],
                    "insurance_providers": [],
                },
            )
            if created:
                logger.info(f"Created therapist profile for user {instance.id}")

        elif user_type == "patient":
            # Get the PatientProfile model dynamically
            try:
                PatientProfile = apps.get_model("patient", "PatientProfile")
                patient_profile, created = PatientProfile.objects.get_or_create(
                    user=instance,
                    defaults={
                        "date_of_birth": None,
                        "emergency_contact": "",
                        "medical_history": "",
                    },
                )
                if created:
                    logger.info(f"Created patient profile for user {instance.id}")
            except LookupError:
                # PatientProfile model doesn't exist yet, skip creation
                logger.warning(
                    "PatientProfile model not found, skipping profile creation"
                )

        return instance


class UserSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(source="patientprofile", read_only=True)
    therapist_profile = TherapistProfileSerializer(read_only=True)
    preferences = UserPreferencesSerializer(read_only=True)
    settings = UserSettingsSerializer(read_only=True)
    profile_id = serializers.SerializerMethodField()

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
            "patient_profile",
            "therapist_profile",
            "profile_id",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]
        extra_kwargs = {"password": {"write_only": True}}

    def get_profile_id(self, obj):
        if (
            obj.user_type == "patient"
            and hasattr(obj, "patient_profile")
            and obj.patient_profile
        ):
            return obj.patient_profile.id
        elif (
            obj.user_type == "therapist"
            and hasattr(obj, "therapist_profile")
            and obj.therapist_profile
        ):
            return obj.therapist_profile.id
        return None

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user


class UserRegistrationSerializer(serializers.ModelSerializer):
    ACCOUNT_TYPE_CHOICES = [
        ("INDIVIDUAL", "Individual"),
        ("ORGANIZATION", "Organization"),
        ("PROFESSIONAL", "Professional"),
    ]

    password = serializers.CharField(
        write_only=True,
        style={
            "input_type": "password",
            "template": "rest_framework/vertical/password.html",
            "placeholder": "********",
        },
        help_text="Enter a secure password with at least 8 characters",
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={
            "input_type": "password",
            "template": "rest_framework/vertical/password.html",
            "placeholder": "********",
        },
        help_text="Re-enter your password for confirmation",
    )
    email = serializers.EmailField(
        style={
            "template": "rest_framework/vertical/input.html",
            "placeholder": "user@example.com",
            "autofocus": True,
        },
        help_text="Enter a valid email address. This will be used for login.",
    )
    user_type = serializers.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES,
        style={
            "base_template": "radio.html",
            "template": "rest_framework/vertical/radio.html",
            "inline": True,
        },
        help_text="Select your role in the system",
        label="User Role",
    )
    account_type = serializers.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        default="INDIVIDUAL",
        style={
            "base_template": "select.html",
            "template": "rest_framework/vertical/select.html",
        },
        help_text="Select your account type",
        required=False,
    )
    first_name = serializers.CharField(
        required=False,
        style={"template": "rest_framework/vertical/input.html", "placeholder": "John"},
        help_text="Your first name",
    )
    last_name = serializers.CharField(
        required=False,
        style={"template": "rest_framework/vertical/input.html", "placeholder": "Doe"},
        help_text="Your last name",
    )

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "user_type",
            "account_type",
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": True},
            "user_type": {"required": True},
            "username": {
                "help_text": "Choose a unique username. If not provided, email will be used.",
                "required": False,
                "style": {
                    "template": "rest_framework/vertical/input.html",
                    "placeholder": "johndoe",
                },
            },
        }

    def validate(self, data):
        if data["password"] != data.pop("confirm_password"):
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            email=validated_data["email"],
            username=validated_data.get("username", validated_data["email"]),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            user_type=validated_data.get("user_type", "patient"),
        )
        return user


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'user_type']
        read_only_fields = ['id', 'username', 'user_type']

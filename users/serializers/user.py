# users/serializers/user.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .profile import PatientProfileSerializer, TherapistProfileSerializer
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
    user_type = serializers.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES,
        style={"base_template": "radio.html"},
        help_text="Select your role in the system. This can only be set once.",
        label="User Role",
    )

    class Meta:
        model = CustomUser
        fields = ["user_type"]
        read_only_fields = ["id", "email"]  # Prevent other fields from being updated

    def validate_user_type(self, value):
        valid_types = [choice[0] for choice in CustomUser.USER_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid user type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def update(self, instance, validated_data):
        instance.user_type = validated_data.get("user_type", instance.user_type)
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(source="patientprofile", read_only=True)
    therapist_profile = TherapistProfileSerializer(source="therapistprofile", read_only=True)
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
            "patient_profile",
            "therapist_profile",
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

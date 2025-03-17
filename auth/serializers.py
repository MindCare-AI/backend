# auth\serializers.py
from dj_rest_auth.serializers import (
    PasswordResetConfirmSerializer,
    UserDetailsSerializer,
)
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from dj_rest_auth.registration.serializers import RegisterSerializer
from allauth.account.adapter import get_adapter
from allauth.account.utils import setup_user_email
import logging

logger = logging.getLogger(__name__)

UserModel = get_user_model()


class CustomPasswordResetConfirmSerializer(PasswordResetConfirmSerializer):
    new_password1 = serializers.CharField(
        max_length=128,
        write_only=True,
        label="New Password",
        style={"input_type": "password"},
    )
    new_password2 = serializers.CharField(
        max_length=128,
        write_only=True,
        label="Confirm New Password",
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        password1 = attrs.get("new_password1")
        password2 = attrs.get("new_password2")
        if password1 != password2:
            raise serializers.ValidationError(
                {"new_password2": "The two password fields didn't match."}
            )
        return super().validate(attrs)

    def save(self):
        if self.set_password_form.is_valid():
            self.set_password_form.save()
            return self.set_password_form.user
        raise serializers.ValidationError(
            "An error occurred while resetting the password."
        )

    def get_user_data(self):
        """Get user data after password reset to return useful profile information"""
        user = self.user
        return {
            "user_id": user.id,
            "email": user.email,
            "user_type": user.user_type,
            "has_profile": hasattr(user, f"{user.user_type}_profile")
            if user.user_type
            else False,
        }


class CustomRegisterSerializer(RegisterSerializer):
    USER_TYPE_CHOICES = [
        ("patient", "Patient"),
        ("therapist", "Therapist"),
        ("", "Choose later"),
    ]

    user_type = serializers.ChoiceField(
        choices=USER_TYPE_CHOICES,
        required=False,  # Make it optional
        default="",  # Default to empty
        help_text="Account type (patient or therapist, can be set later)",
    )

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["user_type"] = self.validated_data.get("user_type", "")
        return data

    def validate_user_type(self, value):
        # Allow empty value for now
        if value and value not in ["patient", "therapist", ""]:
            raise serializers.ValidationError(
                "Invalid user type. Must be 'patient' or 'therapist'"
            )
        return value


class CustomUserDetailsSerializer(UserDetailsSerializer):
    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ("first_name", "last_name")


class CustomEmailRegisterSerializer(RegisterSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    def get_cleaned_data(self):
        return {
            "username": self.validated_data.get("username", ""),
            "password1": self.validated_data.get("password1", ""),
            "email": self.validated_data.get("email", ""),
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
        }

    def save(self, request):
        try:
            adapter = get_adapter()
            user = adapter.new_user(request)
            self.cleaned_data = self.get_cleaned_data()
            user = adapter.save_user(request, user, self, commit=False)
            user.save()
            setup_user_email(request, user, [])
            logger.info(f"Successfully registered user: {user.email}")
            return user
        except Exception as e:
            logger.error(
                f"Registration failed for email {self.cleaned_data.get('email')}: {str(e)}"
            )
            raise


class CustomPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_password_form = None

    def validate(self, data):
        if data["password1"] != data["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )

        try:
            user = UserModel.objects.get(email=data["email"])
            self.set_password_form = SetPasswordForm(
                user=user,
                data={
                    "new_password1": data["password1"],
                    "new_password2": data["password2"],
                },
            )

            if not self.set_password_form.is_valid():
                raise serializers.ValidationError(self.set_password_form.errors)

        except UserModel.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No user found with this email address."}
            )

        return data

    def save(self):
        if not hasattr(self, "set_password_form") or self.set_password_form is None:
            raise serializers.ValidationError("Password reset form not initialized.")

        if self.set_password_form.is_valid():
            self.set_password_form.save()
            return self.set_password_form.user

        raise serializers.ValidationError("Error resetting password.")

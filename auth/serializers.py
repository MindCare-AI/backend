# auth\serializers.py
from dj_rest_auth.serializers import (
    PasswordResetConfirmSerializer,
    UserDetailsSerializer,
)
from rest_framework import serializers
from django.contrib.auth import get_user_model
from dj_rest_auth.registration.serializers import RegisterSerializer
from users.models import CustomUser

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
            "has_profile": hasattr(user, f"{user.user_type}_profile") if user.user_type else False
        }


class CustomRegisterSerializer(RegisterSerializer):
    USER_TYPE_CHOICES = [
        ('patient', 'Patient'),
        ('therapist', 'Therapist'),
        ('', 'Choose later')
    ]
    
    user_type = serializers.ChoiceField(
        choices=USER_TYPE_CHOICES,
        required=False,  # Make it optional
        default='',  # Default to empty
        help_text="Account type (patient or therapist, can be set later)"
    )
    
    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["user_type"] = self.validated_data.get("user_type", "")
        return data
    
    def validate_user_type(self, value):
        # Allow empty value for now
        if value and value not in ['patient', 'therapist', '']:
            raise serializers.ValidationError("Invalid user type. Must be 'patient' or 'therapist'")
        return value


class CustomUserDetailsSerializer(UserDetailsSerializer):
    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ("first_name", "last_name")
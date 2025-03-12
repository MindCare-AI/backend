# auth/registration/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from allauth.account.adapter import get_adapter
from dj_rest_auth.registration.serializers import RegisterSerializer
from users.models import CustomUser
from django.db import transaction
from allauth.account.models import EmailAddress
from django_otp.plugins.otp_totp.models import (
    TOTPDevice,
)  # Added import for 2FA support
import logging

logger = logging.getLogger(__name__)

class CustomRegisterSerializer(RegisterSerializer):
    """
    Custom serializer for user registration in Mindcare.
    """

    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    user_type = serializers.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES, default="patient"
    )
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
            "user_type"
        ]

    def validate(self, data):
        data = super().validate(data)
        username = data.get("username")
        email = data.get("email")
        if not username or not username.strip():
            username = email
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(
                {"username": "A user with that username already exists."}
            )
        data["username"] = username.strip()
        return data

    def validate_email(self, value):
        """Enhanced email validation with debugging"""
        User = get_user_model()
        email = value.lower().strip()
        
        logger.debug(f"Validating email registration for: {email}")
        
        # Check EmailAddress model
        email_exists = EmailAddress.objects.filter(email__iexact=email).exists()
        if email_exists:
            logger.warning(f"Email already exists in EmailAddress model: {email}")
            raise serializers.ValidationError("This email is already registered.")
            
        # Check User model
        user_exists = User.objects.filter(email__iexact=email).exists()
        if user_exists:
            logger.warning(f"Email already exists in User model: {email}")
            raise serializers.ValidationError("This email is already registered.")
            
        logger.info(f"Email validation passed for: {email}")
        return email

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
            "user_type": self.validated_data.get("user_type", "patient"),
        })
        return data

    @transaction.atomic
    def save(self, request):
        try:
            logger.debug("Starting user registration process")
            
            # Get cleaned data
            cleaned_data = self.get_cleaned_data()
            logger.debug(f"Cleaned data: {cleaned_data}")

            # Create user with transaction
            with transaction.atomic():
                user = super().save(request)
                user.first_name = cleaned_data.get('first_name')
                user.last_name = cleaned_data.get('last_name')
                user.user_type = cleaned_data.get('user_type')
                user.email = cleaned_data.get('email').lower()
                if not user.username:
                    user.username = user.email
                user.save()

                # Create profile based on user type
                if user.user_type == 'patient':
                    from users.models import PatientProfile
                    PatientProfile.objects.create(user=user)
                elif user.user_type == 'therapist':
                    from users.models import TherapistProfile
                    TherapistProfile.objects.create(user=user)

                logger.info(f"Successfully created user and profile: {user.email}")
                return user

        except Exception as e:
            logger.error(f"Error during user registration: {str(e)}")
            raise serializers.ValidationError(str(e))


class ResendEmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for requesting a new confirmation email.
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, email):
        email = get_adapter().clean_email(email)
        if (
            email
            and EmailAddress.objects.filter(email__iexact=email, verified=True).exists()
        ):
            raise serializers.ValidationError("This email has already been verified.")
        return email

    def create(self, validated_data):
        email = validated_data.get("email")
        try:
            email_address = EmailAddress.objects.get(email__iexact=email)
            if not email_address.verified:
                email_address.send_confirmation()
            return email_address
        except EmailAddress.DoesNotExist:
            raise serializers.ValidationError(
                "This email address was not found in our system."
            )


class Enable2FASerializer(serializers.Serializer):
    enable_2fa = serializers.BooleanField(required=True)

    def save(self, user):
        if self.validated_data["enable_2fa"]:
            TOTPDevice.objects.get_or_create(user=user, confirmed=True)
        else:
            TOTPDevice.objects.filter(user=user).delete()

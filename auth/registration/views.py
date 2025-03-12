# auth/registration/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny
from allauth.account.models import (
    EmailConfirmation,
    EmailConfirmationHMAC,
    EmailAddress,
)
from dj_rest_auth.registration.views import RegisterView, ResendEmailVerificationView
from django.core.exceptions import ObjectDoesNotExist
from .serializers import ResendEmailVerificationSerializer, CustomRegisterSerializer
from ..serializers import CustomUserDetailsSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.adapter import get_adapter
from django.urls import reverse
from django.db import transaction, IntegrityError
import logging
from allauth.account.utils import send_email_confirmation

from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)


@extend_schema(
    description="Register a new user. Creates a user object, sends a verification email, and returns registration details.",
    summary="User Registration",
    tags=["Registration"],
)
class CustomRegisterView(RegisterView):
    serializer_class = CustomRegisterSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            user = self.user
            send_email_confirmation(request, user)
            return response
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(
    description="Confirm user email using a confirmation key. Supports both HMAC-based and standard confirmation methods.",
    summary="Confirm Email",
    tags=["Email Confirmation"],
)
class CustomConfirmEmailView(APIView):
    """
    Custom view to handle email confirmation.
    Handles both HMAC and standard confirmation methods.
    """

    permission_classes = [AllowAny]

    def get(self, request, key, *args, **kwargs):
        try:
            # Attempt HMAC-based confirmation
            email_confirmation = EmailConfirmationHMAC.from_key(key)
            if not email_confirmation:
                raise ObjectDoesNotExist

            email_confirmation.confirm(request)
            user = email_confirmation.email_address.user
            refresh = RefreshToken.for_user(user)
            user_data = CustomUserDetailsSerializer(user).data
            return Response(
                {
                    "message": "Email confirmed successfully",
                    "user": user_data,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )

        except ObjectDoesNotExist:
            # Fallback to standard confirmation method
            try:
                email_confirmation = EmailConfirmation.objects.get(key=key)
                email_confirmation.confirm(request)
                user = email_confirmation.email_address.user
                refresh = RefreshToken.for_user(user)
                user_data = CustomUserDetailsSerializer(user).data
                return Response(
                    {
                        "message": "Email confirmed successfully",
                        "user": user_data,
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                    status=status.HTTP_200_OK,
                )

            except EmailConfirmation.DoesNotExist:
                return Response(
                    {"message": "Invalid confirmation key"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {
                    "message": "An error occurred during email confirmation",
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(
    description="Resend email verification link to the provided email address.",
    summary="Resend Email Verification",
    tags=["Email Verification"],
)
class CustomResendEmailVerificationView(ResendEmailVerificationView):
    """
    Custom view to handle resending email verification links.
    """

    permission_classes = [AllowAny]
    serializer_class = ResendEmailVerificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
            return Response(
                {
                    "message": "Verification email resent successfully",
                    "email": serializer.validated_data.get("email"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"message": "Failed to resend verification email", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(
    description="Send a new verification email to the provided email address if it is not already verified.",
    summary="Send Verification Email",
    tags=["Email Verification"],
)
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            email_address = EmailAddress.objects.get(email=email)
            if email_address.verified:
                return Response(
                    {"error": "Email is already verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email_address.send_confirmation(request)
            return Response(
                {"message": "Verification email sent"}, status=status.HTTP_200_OK
            )
        except EmailAddress.DoesNotExist:
            return Response(
                {"error": "Email not found"}, status=status.HTTP_404_NOT_FOUND
            )

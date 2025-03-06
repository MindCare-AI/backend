# auth\registration\views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from dj_rest_auth.registration.views import RegisterView, ResendEmailVerificationView
from django.core.exceptions import ObjectDoesNotExist
from allauth.account.utils import complete_signup
from allauth.account import app_settings
from rest_framework_simplejwt.tokens import RefreshToken
import smtplib
import socket
import logging
from .serializers import CustomRegisterSerializer
from django.db import transaction
from users.models import UserProfile, UserPreferences, UserSettings

logger = logging.getLogger(__name__)


class CustomRegisterView(RegisterView):
    serializer_class = CustomRegisterSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            user = serializer.save(self.request)

            # Create related profiles using get_or_create
            UserProfile.objects.get_or_create(user=user)
            UserPreferences.objects.get_or_create(user=user)
            UserSettings.objects.get_or_create(user=user)

            return user
        except Exception as e:
            logger.error(f"Error in perform_create: {str(e)}", exc_info=True)
            raise

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = self.perform_create(serializer)

            email_status = self._send_verification_email(request, user)

            return Response(
                {
                    "status": "success",
                    "message": "User registered successfully",
                    "user": serializer.data,
                    "email_verification": email_status,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _send_verification_email(self, request, user):
        try:
            complete_signup(request, user, app_settings.EMAIL_VERIFICATION, None)
            return {
                "success": True,
                "message": "Verification email sent successfully, check your email",
                "status_code": status.HTTP_200_OK,
            }
        except (smtplib.SMTPException, socket.error, ConnectionRefusedError) as e:
            logger.error(f"Email sending error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to send verification email: {str(e)}",
                "error_type": e.__class__.__name__,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }


class CustomConfirmEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, key, *args, **kwargs):
        try:
            email_confirmation = EmailConfirmationHMAC.from_key(key)
            if not email_confirmation:
                raise ObjectDoesNotExist
            email_confirmation.confirm(request)
            user = email_confirmation.email_address.user
            refresh = RefreshToken.for_user(user)
            user_data = {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
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
            try:
                email_confirmation = EmailConfirmation.objects.get(key=key)
                email_confirmation.confirm(request)
                return Response(
                    {"message": "Email confirmed successfully"},
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


class CustomResendEmailVerificationView(ResendEmailVerificationView):
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        from dj_rest_auth.registration.serializers import (
            ResendEmailVerificationSerializer,
        )

        return ResendEmailVerificationSerializer

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

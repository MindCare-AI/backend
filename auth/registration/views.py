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
from auth.serializers import CustomRegisterSerializer
from allauth.account.adapter import get_adapter


class CustomRegisterView(RegisterView):
    serializer_class = CustomRegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        return user

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        email_status = {
            "success": True,
            "message": "Verification email sent successfully, check your email",
            "status_code": status.HTTP_200_OK,
        }
        try:
            complete_signup(request, user, app_settings.EMAIL_VERIFICATION, None)
        except (smtplib.SMTPException, socket.error, ConnectionRefusedError) as e:
            email_status = {
                "success": False,
                "message": f"Failed to send verification email: {str(e)}",
                "error_type": e.__class__.__name__,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
        return Response(
            {
                "status": "success",
                "message": "User registered successfully",
                "user": serializer.data,
                "email_verification": email_status,
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def get_response_data(self, user):
        data = super().get_response_data(user)
        return data


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
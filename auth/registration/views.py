# auth\registration\views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from allauth.account.models import (
    EmailConfirmation,
    EmailConfirmationHMAC,
    EmailAddress,
)
from dj_rest_auth.registration.views import ResendEmailVerificationView, RegisterView
from django.core.exceptions import ObjectDoesNotExist
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class CustomRegisterView(RegisterView):
    """
    Enhanced registration view that inherits from dj-rest-auth's RegisterView
    to properly handle email verification and user creation.
    """

    def create(self, request, *args, **kwargs):
        # Let the parent class handle user creation and email verification
        response = super().create(request, *args, **kwargs)

        # Only add custom logic if the registration was successful
        if response.status_code == status.HTTP_201_CREATED:
            try:
                # Get the created user
                user = response.data.get("user", {})
                user_id = user.get("pk") if isinstance(user, dict) else None

                # Enhance response with more user-friendly message
                response.data.update(
                    {
                        "detail": "Registration successful. Please check your email to verify your account.",
                        "user": {
                            "id": user_id,
                            "email": response.data.get("email", ""),
                            "user_type": response.data.get("user_type", None),
                        },
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error enhancing registration response: {str(e)}", exc_info=True
                )

        return response


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
    """
    Custom view for resending email verification.
    Inherits from dj-rest-auth's ResendEmailVerificationView.
    """

    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            email = serializer.validated_data["email"]
            User = get_user_model()

            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                return Response(
                    {"detail": "No user found with this email address."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check if already verified
            if user.emailaddress_set.filter(email=email, verified=True).exists():
                return Response(
                    {"detail": "Email is already verified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get or create EmailAddress
            email_address, created = EmailAddress.objects.get_or_create(
                user=user, email=email, defaults={"verified": False, "primary": True}
            )

            # Send confirmation
            email_address.send_confirmation(request)
            logger.info(f"Verification email resent to {email}")

            return Response(
                {"detail": "Verification email has been sent."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Failed to resend verification email: {str(e)}")
            return Response(
                {"detail": "Failed to resend verification email."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

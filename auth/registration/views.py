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
from dj_rest_auth.registration.views import RegisterView, ResendEmailVerificationView
from django.core.exceptions import ObjectDoesNotExist
from allauth.account.utils import complete_signup
from allauth.account import app_settings
from rest_framework_simplejwt.tokens import RefreshToken
import smtplib
import socket
from auth.serializers import CustomRegisterSerializer
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CustomRegisterView(RegisterView):
    serializer_class = CustomRegisterSerializer

    def perform_create(self, serializer):
        """Create new user with rate limiting"""
        try:
            # Check cache connection
            try:
                cache.get('test_key')
            except Exception as cache_error:
                logger.error(f"Cache connection error: {str(cache_error)}")
                # Continue without caching if Redis is down
                return serializer.save(self.request)

            user = serializer.save(self.request)
            
            # Cache user registration attempt with fallback
            try:
                cache_key = f"registration_attempt_{user.email}"
                cache.set(cache_key, True, timeout=300)  # 5 minutes
            except Exception as e:
                logger.warning(f"Failed to cache registration attempt: {str(e)}")
            
            return user

        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Check for rate limiting
            email = serializer.validated_data.get('email')
            if self._check_rate_limit(email):
                return Response(
                    {"detail": "Too many registration attempts. Please try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            
            user = self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            # Send verification email
            email_status = self._send_verification_email(request, user)
            
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
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response(
                {"detail": "Registration failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _check_rate_limit(self, email):
        """Check registration rate limiting with fallback"""
        if not settings.MAX_REGISTRATION_ATTEMPTS:
            return False

        try:
            cache_key = f"registration_attempts_{email}"
            attempts = cache.get(cache_key, 0)
            
            if attempts >= settings.MAX_REGISTRATION_ATTEMPTS:
                return True
                
            cache.set(
                cache_key, 
                attempts + 1, 
                timeout=getattr(settings, 'EMAIL_VERIFICATION_TIMEOUT', 3600)
            )
            return False
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            # If cache fails, allow registration
            return False

    def _send_verification_email(self, request, user):
        """Send verification email with error handling"""
        try:
            complete_signup(request, user, app_settings.EMAIL_VERIFICATION, None)
            return {
                "success": True,
                "message": "Verification email sent successfully",
                "status_code": status.HTTP_200_OK,
            }
        except (smtplib.SMTPException, socket.error, ConnectionRefusedError) as e:
            logger.error(f"Email sending failed: {str(e)}")
            return {
                "success": False,
                "message": "Failed to send verification email",
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

import logging
from dj_rest_auth.views import PasswordResetConfirmView
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from .serializers import CustomPasswordResetConfirmSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.conf import settings
from urllib.parse import urlencode
from rest_framework.permissions import AllowAny, IsAuthenticated
import secrets
from django_otp.plugins.otp_totp.models import TOTPDevice
from .serializers import Enable2FASerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("new_password1", "new_password2")
)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    serializer_class = CustomPasswordResetConfirmSerializer

    def get(self, request, uidb64=None, token=None):
        if not uidb64 or not token:
            return Response(
                {"error": "UID and token are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.session["uid"] = uidb64
        request.session["token"] = token
        return Response(
            {"message": "UID and token stored in session. Enter new passwords."},
            status=status.HTTP_200_OK,
        )

    @sensitive_post_parameters_m
    def post(self, request, *args, **kwargs):
        uid = request.session.get("uid")
        token = request.session.get("token")
        if not uid or not token:
            return Response(
                {"error": "Reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data.copy()
        data["uid"] = uid
        data["token"] = token
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        request.session.pop("uid", None)
        request.session.pop("token", None)
        return Response(
            {"message": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_OAUTH_REDIRECT_URI
    client_class = OAuth2Client

    def get_response(self):
        response = super().get_response()
        if self.token:
            response.data["access_token"] = str(self.token.access_token)
            response.data["refresh_token"] = str(self.token)
        return response


class GitHubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter


class GoogleAuthRedirect(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            state = secrets.token_urlsafe(32)
            request.session["oauth_state"] = state
            google_settings = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]
            params = {
                "client_id": google_settings["client_id"],
                "response_type": "code",
                "scope": "openid email profile",
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            )
            return Response({"authorization_url": auth_url}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Google OAuth error: {str(e)}")
            return Response(
                {
                    "error": "Failed to initialize Google authentication",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoogleCallback(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        stored_state = request.session.pop("oauth_state", None)
        if not state or state != stored_state:
            return Response(
                {"error": "Invalid state parameter"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not code:
            return Response(
                {"error": "Authorization code not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"code": code, "message": "Authorization successful"})


@extend_schema(
    description="Enable or disable 2FA for the authenticated user.",
    summary="Enable/Disable 2FA",
    tags=["2FA"],
)
class Enable2FAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = Enable2FASerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "2FA settings updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

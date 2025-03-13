# auth\views.py
import logging
from dj_rest_auth.views import PasswordResetConfirmView
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from .serializers import CustomPasswordResetConfirmSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.conf import settings
from django.http import HttpResponseRedirect
from urllib.parse import urlencode

# Decorator for sensitive post parameters
sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("new_password1", "new_password2")
)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Custom password reset confirmation view for Mindcare.
    Stores and retrieves UID and token from the session.
    """

    serializer_class = CustomPasswordResetConfirmSerializer

    @sensitive_post_parameters_m
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
        
        # Get user information to return in response
        user_data = serializer.get_user_data() if hasattr(serializer, 'get_user_data') else {}
        
        # Clear session data
        request.session.pop("uid", None)
        request.session.pop("token", None)
        
        # Return enhanced response with user data
        return Response(
            {
                "message": "Password has been reset successfully.",
                "user": user_data
            },
            status=status.HTTP_200_OK,
        )


logger = logging.getLogger(__name__)


class GoogleLogin(SocialLoginView):  # Using Authorization Code Grant
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:8000/api/v1/auth/login/google/callback/"
    client_class = OAuth2Client
    
    def post(self, request, *args, **kwargs):
        # Extract user_type from request if available
        user_type = request.data.get('user_type', 'patient')
        request.user_type = user_type  # Store for the adapter to use
        
        response = super().post(request, *args, **kwargs)
        
        # Add profile information to response
        if response.status_code == 200 and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            profile_info = {
                "user_id": user.id,
                "email": user.email,
                "user_type": user.user_type,
                "has_profile": hasattr(user, f"{user.user_type}_profile")
            }
            response.data["user_profile"] = profile_info
            
        return response


class GoogleAuthRedirect(APIView):
    def get(self, request):
        try:
            google_settings = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]
            client_id = google_settings["client_id"]
            redirect_uri = "http://localhost:8000/api/v1/auth/login/google/callback/"
            base_url = "https://accounts.google.com/o/oauth2/v2/auth"
            params = {
                "redirect_uri": redirect_uri,
                "prompt": "consent",
                "response_type": "code",
                "client_id": client_id,
                "scope": "openid email profile",
                "access_type": "offline",
            }
            auth_url = f"{base_url}?{urlencode(params)}"
            return HttpResponseRedirect(auth_url)
        except Exception as e:
            logger.error(e)
            return Response(
                {"error": "An error occurred during Google authentication."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
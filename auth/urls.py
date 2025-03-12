# auth\urls.py
from django.urls import path, re_path
from auth.registration.views import (
    CustomConfirmEmailView,
    CustomRegisterView,
    ResendVerificationEmailView,
    CustomResendEmailVerificationView,
)
from dj_rest_auth.views import (
    PasswordResetView,
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from dj_rest_auth.registration.views import VerifyEmailView
from auth.views import (
    CustomPasswordResetConfirmView,
    GoogleLogin,
    GoogleAuthRedirect,
    GitHubLogin,
    GoogleCallback,
    Enable2FAView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from auth.registration.custom_adapter import FacebookLogin, LinkedInLogin

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", CustomRegisterView.as_view(), name="rest_register"),
    path("password/reset/", PasswordResetView.as_view(), name="password_reset"),
    re_path(
        r"^password/reset/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z\-_]+)/$",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("email/verify/", VerifyEmailView.as_view(), name="verify_email"),
    path(
        "email/verify/resend/",
        ResendVerificationEmailView.as_view(),
        name="resend_email_verification",
    ),
    re_path(
        r"^email/confirm/(?P<key>[-:\w]+)/$",
        CustomConfirmEmailView.as_view(),
        name="account_confirm_email",
    ),
    path("login/google/", GoogleLogin.as_view(), name="google_login"),
    path(
        "login/google/start/", GoogleAuthRedirect.as_view(), name="google_auth_redirect"
    ),
    path("login/github/", GitHubLogin.as_view(), name="github_login"),
    path("login/google/callback/", GoogleCallback.as_view(), name="google_callback"),
    # New endpoints
    path("login/facebook/", FacebookLogin.as_view(), name="facebook_login"),
    path("login/linkedin/", LinkedInLogin.as_view(), name="linkedin_login"),
    path("enable-2fa/", Enable2FAView.as_view(), name="enable_2fa"),
    path('confirm-email/<str:key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    path('resend-email-verification/', CustomResendEmailVerificationView.as_view(), name='rest_resend_email_verification'),
    path('send-verification-email/', ResendVerificationEmailView.as_view(), name='send_verification_email'),
]

#auth\urls.py
from django.urls import path, re_path
from auth.registration.views import (
    CustomConfirmEmailView,
    CustomRegisterView,
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
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", CustomRegisterView.as_view(), name="register"),
    path("password/reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/confirm/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("email/verify/", VerifyEmailView.as_view(), name="verify_email"),
    path("email/verify/resend/", CustomResendEmailVerificationView.as_view(), name="resend_email_verification"),
    re_path(r"^email/confirm/(?P<key>[-:\w]+)/$", CustomConfirmEmailView.as_view(), name="account_confirm_email"),
    path("login/google/", GoogleLogin.as_view(), name="google_login"),
    path("login/google/start/", GoogleAuthRedirect.as_view(), name="google_auth_redirect"),
]

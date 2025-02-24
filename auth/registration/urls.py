# auth\registration\urls.py
from django.urls import path
from .views import (
    CustomRegisterView,
    CustomConfirmEmailView,
    CustomResendEmailVerificationView,
)

urlpatterns = [
    path("register/", CustomRegisterView.as_view(), name="register"),
    path(
        "email/confirm/<str:key>/",
        CustomConfirmEmailView.as_view(),
        name="account_confirm_email",
    ),
    path(
        "email/verify/resend/",
        CustomResendEmailVerificationView.as_view(),
        name="resend_email_verification",
    ),
]

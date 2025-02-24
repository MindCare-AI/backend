#auth\registration\custom_adapter.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
import smtplib
import socket
from rest_framework.response import Response

class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for saving additional user fields during registration.
    """

    def save_user(self, request, user, form, commit=True):
        # Use cleaned_data if available
        data = getattr(form, "cleaned_data", form)
        user.username = data.get("username", user.username)
        user.email = data.get("email", user.email)
        user.first_name = data.get("first_name", user.first_name or "")
        user.last_name = data.get("last_name", user.last_name or "")
        # Removed country, region, and phone_number for Mindcare
        password = data.get("password1", None)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user

    def send_mail(self, template_prefix, email, context):
        try:
            msg = self.render_mail(template_prefix, email, context)
            msg.send()
        except (smtplib.SMTPException, socket.error, ConnectionRefusedError) as e:
            raise e

    def respond_email_verification_sent(self, request, user):
        return Response(
            {"detail": "Email verification sent, please check your email"},
            status=200,
        )


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.save()
        return user

# auth\registration\custom_adapter.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from allauth.account.models import EmailConfirmationHMAC
from django.contrib.sites.shortcuts import get_current_site
import logging

from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.linkedin_oauth2.views import LinkedInOAuth2Adapter

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for handling user registration and email confirmation.
    """

    def save_user(self, request, user, form, commit=True):
        """
        Save user during registration with additional fields.
        """
        data = getattr(form, "cleaned_data", form)
        user.username = data.get("username", user.username)
        user.email = data.get("email", user.email)
        user.first_name = data.get("first_name", user.first_name or "")
        user.last_name = data.get("last_name", user.last_name or "")
        password = data.get("password1", None)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user

    def send_mail(self, template_prefix, email, context):
        """
        Send email with detailed logging.
        """
        try:
            logger.info(f"Preparing to send email to: {email}")
            logger.debug(f"Using template prefix: {template_prefix}")
            logger.debug(f"Email context keys: {context.keys()}")

            msg = self.render_mail(template_prefix, email, context)
            logger.debug(f"Email subject: {msg.subject}")
            logger.debug(f"Email body: {msg.body}")
            msg.send()
            logger.info(f"Email sent successfully to {email}")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise

    def send_confirmation_mail(self, request, emailaddress, signup=False):
        """
        Send confirmation email with proper logging and error handling.
        """
        try:
            logger.info(
                f"Preparing to send confirmation email to: {emailaddress.email}"
            )

            # Ensure the email address has a user associated with it
            if not hasattr(emailaddress, "user"):
                logger.error(
                    f"EmailAddress {emailaddress.email} has no associated user"
                )
                raise ValueError("EmailAddress has no associated user")

            # Create email confirmation
            email_confirmation = EmailConfirmationHMAC(emailaddress)

            # Get current site
            current_site = get_current_site(request)

            # Prepare context for email template
            context = {
                "user": emailaddress.user,  # Access the user from the email address
                "activate_url": self.get_email_confirmation_url(
                    request, email_confirmation
                ),
                "current_site": current_site,
                "key": email_confirmation.key,
            }

            logger.debug(f"Email context prepared: {context}")

            # Send the confirmation email
            self.send_mail(
                template_prefix="account/email/email_confirmation",
                email=emailaddress.email,
                context=context,
            )

            logger.info(f"Confirmation email sent successfully to {emailaddress.email}")
            return email_confirmation

        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")
            raise

    def respond_email_verification_sent(self, request, user):
        """
        Handles the response after sending verification email.
        For API requests returns JSON, for regular requests redirects.
        """
        if self.is_api_request(request):
            return JsonResponse(
                {
                    "detail": "Email verification sent, please check your email",
                    "email": user.email,
                },
                status=200,
            )

        # Default behavior for non-API requests
        return HttpResponseRedirect(reverse("account_email_verification_sent"))

    def is_api_request(self, request):
        """
        Determines if the request is an API request based on headers or path.
        """
        return request.headers.get("Accept", "").startswith(
            "application/json"
        ) or request.path.startswith("/api/")


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for handling social account registration.
    """

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.save()
        return user


class FacebookLogin(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter


class LinkedInLogin(SocialLoginView):
    adapter_class = LinkedInOAuth2Adapter

# auth\registration\custom_adapter.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
import smtplib
import socket
from rest_framework.response import Response
from patient.models.patient_profile import PatientProfile  # Updated import
from therapist.models.therapist_profile import TherapistProfile  # Updated import
import logging

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for saving additional user fields during registration.
    """

    def save_user(self, request, user, form, commit=True):
        # Let the parent class handle basic user setup
        user = super().save_user(request, user, form, commit=False)

        # Get data from form (either cleaned_data or form directly)
        data = getattr(form, "cleaned_data", form)

        # Add custom fields - user_type isn't handled by parent class
        user.user_type = data.get("user_type", None)

        if commit:
            user.save()

            # Create profile based on user_type
            try:
                if user.user_type == "patient":
                    PatientProfile.objects.create(user=user, profile_type="patient")
                elif user.user_type == "therapist":
                    TherapistProfile.objects.create(user=user, profile_type="therapist")
            except Exception as e:
                logger.error(f"Error creating profile during registration: {str(e)}")

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

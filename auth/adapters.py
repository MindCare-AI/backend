from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from users.models import PatientProfile, TherapistProfile
import logging

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        """
        Saves a new user and creates corresponding profile based on user_type
        """
        data = form.cleaned_data
        user = super().save_user(request, user, form, commit=False)
        user.user_type = data.get("user_type")

        if commit:
            user.save()
            # Create appropriate profile
            try:
                if user.user_type == "patient":
                    PatientProfile.objects.create(user=user, profile_type="patient")
                elif user.user_type == "therapist":
                    TherapistProfile.objects.create(user=user, profile_type="therapist")
            except Exception as e:
                logger.error(f"Error creating profile: {str(e)}")

        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        """
        Handle social account registration with profile creation
        """
        # Default social users to patients if not specified
        user_type = getattr(request, "user_type", "patient")

        user = super().save_user(request, sociallogin, form)
        user.user_type = user_type
        user.save()

        # Create appropriate profile
        try:
            if user.user_type == "patient":
                PatientProfile.objects.get_or_create(
                    user=user, defaults={"profile_type": "patient"}
                )
            elif user.user_type == "therapist":
                TherapistProfile.objects.get_or_create(
                    user=user, defaults={"profile_type": "therapist"}
                )
        except Exception as e:
            logger.error(f"Error creating profile for social user: {str(e)}")

        return user

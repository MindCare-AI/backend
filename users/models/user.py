# users/models/user.py
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import logging
from model_utils import FieldTracker
from django.apps import apps
from appointments.models import Appointment

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ("patient", "Patient"),
        ("therapist", "Therapist"),
    ]

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        blank=True,
        null=True,
        default="patient",
    )
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    crisis_alert_enabled = models.BooleanField(default=True)
    passcode_enabled = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False, null=False)

    tracker = FieldTracker(
        ["user_type", "email", "phone_number", "crisis_alert_enabled"]
    )

    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Save user and create corresponding profile if needed"""
        creating = self._state.adding
        old_type = None

        if not creating:
            try:
                old_type = type(self).objects.get(pk=self.pk).user_type
            except type(self).DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Handle profile creation/updates
        if creating and self.user_type:
            self._create_profile()
        elif not creating and old_type != self.user_type:
            self._handle_user_type_change(old_type)

    def get_profile_model(self, user_type):
        """Get the appropriate profile model based on user type"""
        if user_type == "patient":
            return apps.get_model("patient", "PatientProfile")
        elif user_type == "therapist":
            return apps.get_model("therapist", "TherapistProfile")
        return None

    def _create_profile(self):
        """Create corresponding profile based on user type"""
        try:
            ProfileModel = self.get_profile_model(self.user_type)
            if ProfileModel:
                ProfileModel.objects.create(user=self)
        except Exception as e:
            logger.error(f"Error creating profile for user {self.id}: {str(e)}")
            raise

    def _handle_user_type_change(self, old_type):
        """Handle user type changes by updating profiles"""
        try:
            # Delete old profile and dependent appointments
            OldProfileModel = self.get_profile_model(old_type)
            if OldProfileModel:
                if old_type == "therapist":
                    # Delete appointments linked to the old therapist profile
                    Appointment.objects.filter(
                        therapist=self.therapist_profile
                    ).delete()
                elif old_type == "patient":
                    # Delete appointments linked to the old patient profile
                    Appointment.objects.filter(patient=self.patient_profile).delete()
                OldProfileModel.objects.filter(user=self).delete()

            # Create new profile if needed
            if self.user_type:
                self._create_profile()
        except Exception as e:
            logger.error(
                f"Error handling user type change for user {self.id}: {str(e)}"
            )
            raise

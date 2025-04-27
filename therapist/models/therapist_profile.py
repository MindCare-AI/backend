# therapist/models/therapist_profile.py
import logging
from datetime import datetime, timedelta
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from appointments.models import Appointment

logger = logging.getLogger(__name__)


class TherapistProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapist_profile",
    )
    bio = models.TextField(blank=True)
    specializations = models.JSONField(default=list)
    education = models.JSONField(default=list)
    experience = models.JSONField(default=list)
    years_of_experience = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    license_number = models.CharField(max_length=100, unique=True)
    license_expiry = models.DateField()
    available_days = models.JSONField(
        default=dict, help_text="Dictionary of available days and time slots"
    )
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    profile_completion = models.FloatField(default=0)

    # Verification Status
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("verified", "Verified"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    verification_notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_documents = models.JSONField(default=list)
    profile_picture = models.ImageField(
        upload_to="therapist_profile_pics/", null=True, blank=True
    )
    rating = models.FloatField(
        default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    total_ratings = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    languages = models.JSONField(
        default=list, help_text="List of languages spoken by the therapist"
    )
    therapy_types = models.JSONField(default=list, help_text="Types of therapy offered")
    accepts_insurance = models.BooleanField(default=False)
    insurance_providers = models.JSONField(
        default=list, help_text="List of accepted insurance providers"
    )
    session_duration = models.JSONField(
        default=list, help_text="Available session durations in minutes"
    )

    def __str__(self):
        return f"Therapist Profile - {self.user.username}"

    def clean(self):
        super().clean()

        if self.license_expiry and self.license_expiry < timezone.now().date():
            raise ValidationError(
                {"license_expiry": "License expiry date cannot be in the past"}
            )

        if self.years_of_experience < 0:
            raise ValidationError(
                {"years_of_experience": "Years of experience cannot be negative"}
            )

        if self.available_days:
            try:
                valid_days = {
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                }
                for day, slots in self.available_days.items():
                    if day.lower() not in valid_days:
                        raise ValidationError(f"Invalid day: {day}")

                    if not isinstance(slots, list):
                        raise ValidationError(f"Schedule for {day} must be a list")

                    for slot in slots:
                        if (
                            not isinstance(slot, dict)
                            or "start" not in slot
                            or "end" not in slot
                        ):
                            raise ValidationError(f"Invalid time slot format in {day}")

                        try:
                            datetime.strptime(slot["start"], "%H:%M")
                            datetime.strptime(slot["end"], "%H:%M")
                        except ValueError:
                            raise ValidationError(
                                f"Invalid time format in {day}. Use HH:MM format"
                            )
            except AttributeError:
                raise ValidationError("available_days must be a dictionary")
            except Exception as e:
                raise ValidationError(f"Invalid available_days format: {str(e)}")

    def save(self, *args, **kwargs):
        if not self.pk:  # New instance
            self.profile_completion = self._calculate_profile_completion()
        super().save(*args, **kwargs)

    def _calculate_profile_completion(self):
        """Calculate profile completion percentage"""
        required_fields = {
            "bio": bool(self.bio),
            "specializations": bool(self.specializations),
            "education": bool(self.education),
            "experience": bool(self.experience),
            "years_of_experience": bool(self.years_of_experience),
            "license_number": bool(self.license_number),
            "license_expiry": bool(self.license_expiry),
            "available_days": bool(self.available_days),
            "languages": bool(self.languages),
            "therapy_types": bool(self.therapy_types),
            "profile_picture": bool(self.profile_picture),
        }

        completed = sum(required_fields.values())
        total = len(required_fields)
        return (completed / total) * 100

    def check_availability(self, date_time, duration=60):
        if not self.available_days:
            return False

        day = date_time.strftime("%A").lower()

        if day not in self.available_days:
            return False

        time = date_time.time()
        end_time = (date_time + timedelta(minutes=duration)).time()

        for slot in self.available_days[day]:
            slot_start = datetime.strptime(slot["start"], "%H:%M").time()
            slot_end = datetime.strptime(slot["end"], "%H:%M").time()

            if slot_start <= time and end_time <= slot_end:
                conflicting_appointments = Appointment.objects.filter(
                    therapist=self,
                    appointment_date__range=(
                        date_time,
                        date_time + timedelta(minutes=duration),
                    ),
                    status__in=["scheduled", "confirmed"],
                ).exists()

                return not conflicting_appointments

        return False

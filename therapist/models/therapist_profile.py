# therapist/models/therapist_profile.py
import logging
from datetime import datetime, timedelta, date
from django.db import models
from django.db.models import Q
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
    education = models.JSONField(
        default=list, help_text="List of educational qualifications"
    )
    experience = models.JSONField(default=list, null=True, blank=True)
    years_of_experience = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
    )
    license_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default="",  # Add default empty string
        help_text="Professional license number (can be added later)",
    )
    license_expiry = models.DateField(null=True, blank=True)
    available_days = models.JSONField(
        default=dict, help_text="Dictionary of available days and time slots"
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    profile_completion = models.FloatField(default=0)
    video_session_link = models.URLField(max_length=500, blank=True, null=True)

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

    # Practice Details
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
    session_duration = models.PositiveIntegerField(
        default=60,
        help_text="Default session duration in minutes",
        validators=[MinValueValidator(15), MaxValueValidator(180)],
    )

    class Meta:
        ordering = ["user__username"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["is_verified", "verification_status"]),
        ]
        # Add a custom constraint that only enforces uniqueness when license_number is not null
        constraints = [
            models.UniqueConstraint(
                fields=["license_number"],
                condition=models.Q(license_number__isnull=False)
                & ~models.Q(license_number__exact=""),
                name="unique_license_number_when_not_null",
            )
        ]

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
                            start_time = datetime.strptime(
                                slot["start"], "%H:%M"
                            ).time()
                            end_time = datetime.strptime(slot["end"], "%H:%M").time()
                            if start_time >= end_time:
                                raise ValidationError(
                                    f"Start time must be before end time in {day}"
                                )
                        except ValueError:
                            raise ValidationError(
                                f"Invalid time format in {day}. Use HH:MM format"
                            )
            except AttributeError:
                raise ValidationError("available_days must be a dictionary")
            except Exception as e:
                raise ValidationError(f"Invalid available_days format: {str(e)}")

    def save(self, *args, **kwargs):
        # Convert empty string to None to avoid unique constraint violations
        if self.license_number == "":
            self.license_number = None

        # Ensure experience is never None - convert to empty list
        if self.experience is None:
            self.experience = []

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
            "hourly_rate": bool(self.hourly_rate),
            "accepts_insurance": bool(self.accepts_insurance),
            "insurance_providers": bool(self.insurance_providers),
            "session_duration": bool(self.session_duration),
            "video_session_link": bool(self.video_session_link),
        }

        completed = sum(required_fields.values())
        total = len(required_fields)
        return (completed / total) * 100 if total > 0 else 0

    def check_availability(self, date_time, duration=60):
        if not self.available_days:
            return False

        day = date_time.strftime("%A").lower()

        if day not in self.available_days:
            return False

        requested_start_time = date_time.time()
        requested_end_time = (date_time + timedelta(minutes=duration)).time()
        requested_date = date_time.date()

        is_slot_available = False
        for slot in self.available_days[day]:
            slot_start = datetime.strptime(slot["start"], "%H:%M").time()
            slot_end = datetime.strptime(slot["end"], "%H:%M").time()

            if slot_start <= requested_start_time and requested_end_time <= slot_end:
                is_slot_available = True
                break

        if not is_slot_available:
            return False

        requested_start_datetime = timezone.make_aware(
            datetime.combine(requested_date, requested_start_time)
        )
        requested_end_datetime = timezone.make_aware(
            datetime.combine(requested_date, requested_end_time)
        )

        conflicting_appointments = (
            Appointment.objects.filter(
                therapist=self,
                appointment_date__date=requested_date,
                status__in=["scheduled", "confirmed"],
            )
            .filter(
                Q(appointment_date__lt=requested_end_datetime)
                & Q(
                    appointment_date__gte=requested_start_datetime
                    - timedelta(minutes=duration)
                )
            )
            .exists()
        )

        return not conflicting_appointments

    def get_available_days(self):
        # Example: return next 7 weekdays starting tomorrow
        available = []
        current = date.today() + timedelta(days=1)
        while len(available) < 7:
            if current.weekday() < 5:  # Monday-Friday
                available.append(current)
            current += timedelta(days=1)
        return available

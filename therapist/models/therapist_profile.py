# therapist/models/therapist_profile.py
import logging
from datetime import datetime, timedelta
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from .appointment import Appointment

logger = logging.getLogger(__name__)


class TherapistProfile(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapist_profile",
    )

    specialization = models.CharField(max_length=100, blank=True, default="")
    license_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="License number format: AA-123456",
    )
    years_of_experience = models.IntegerField(
        validators=[MinValueValidator(0)], default=0
    )

    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(
        upload_to="therapist_profile_pics/", null=True, blank=True
    )

    treatment_approaches = models.JSONField(
        default=list,
        blank=True,
        help_text="List of therapy methods and approaches used",
    )
    available_days = models.JSONField(
        default=dict, blank=True, null=True, help_text="Weekly availability schedule"
    )
    license_expiry = models.DateField(blank=True, null=True)
    video_session_link = models.URLField(blank=True, null=True)
    languages_spoken = models.JSONField(
        default=list,
        blank=True,
        help_text="Languages the therapist can conduct sessions in",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_profile_complete = models.BooleanField(default=False)
    profile_completion_percentage = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("verified", "Verified"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    verification_notes = models.TextField(blank=True, null=True)
    verification_documents = models.FileField(
        upload_to="verification_docs/", null=True, blank=True
    )
    last_verification_attempt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "therapist_profile"
        verbose_name = "Therapist Profile"
        verbose_name_plural = "Therapist Profiles"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["specialization"]),
            models.Index(fields=["is_verified"]),
        ]
        app_label = "therapist"

    def __str__(self):
        return f"Therapist: {self.user.get_full_name() or self.user.email}"

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
        self.clean()
        self._calculate_profile_completion()
        super().save(*args, **kwargs)

    def _calculate_profile_completion(self):
        field_weights = {
            "specialization": 2,
            "license_number": 3,
            "bio": 1,
            "profile_pic": 1,
            "treatment_approaches": 2,
            "available_days": 2,
            "video_session_link": 1,
            "languages_spoken": 1,
        }

        if self.license_number:
            field_weights["license_expiry"] = 2

        total_weight = sum(field_weights.values())
        weighted_score = 0

        for field, weight in field_weights.items():
            field_value = getattr(self, field)

            if isinstance(field_value, (dict, list)) and not field_value:
                continue

            if field == "license_expiry" and self.license_number:
                if field_value and field_value > timezone.now().date():
                    weighted_score += weight
            elif field_value:
                weighted_score += weight

        self.profile_completion_percentage = int((weighted_score / total_weight) * 100)

        required_fields = {
            "specialization": bool(self.specialization),
            "license_number": bool(self.license_number),
            "license_expiry": bool(self.license_expiry)
            if self.license_number
            else True,
            "available_days": bool(self.available_days),
        }

        self.is_profile_complete = self.profile_completion_percentage >= 80 and all(
            required_fields.values()
        )

        logger.debug(
            f"Profile completion for {self.user.username}: {self.profile_completion_percentage}%, "
            f"Complete: {self.is_profile_complete}"
        )

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

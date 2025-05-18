from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.crypto import get_random_string
from datetime import timedelta, datetime, time
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from messaging.models.one_to_one import OneToOneConversation


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
        ("missed", "Missed"),
    ]

    appointment_id = models.CharField(max_length=10, unique=True, editable=False)
    patient = models.ForeignKey(
        "patient.PatientProfile", on_delete=models.CASCADE, related_name="appointments"
    )
    therapist = models.ForeignKey(
        "therapist.TherapistProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    appointment_date = models.DateTimeField()
    duration = models.DurationField(default=timedelta(minutes=60))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    notes = models.TextField(blank=True)
    video_session_link = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_appointments",
    )
    cancellation_reason = models.TextField(blank=True)
    reminder_sent = models.BooleanField(default=False)

    # Fields for rescheduling tracking
    original_date = models.DateTimeField(null=True, blank=True)
    reschedule_count = models.PositiveIntegerField(default=0)
    last_rescheduled = models.DateTimeField(null=True, blank=True)
    rescheduled_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # Explicitly set blank=True to make it optional in forms/validation
        related_name="rescheduled_appointments",
    )

    ai_recommendations = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI-generated recommendations for the therapy session",
    )

    pain_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Patient's pain level (0-10) reported during appointment",
    )

    class Meta:
        ordering = ["-appointment_date"]
        indexes = [
            models.Index(fields=["appointment_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["therapist", "status"]),
            models.Index(fields=["therapist", "appointment_date"]),
            models.Index(fields=["patient", "appointment_date"]),
        ]

    def __str__(self):
        return (
            f"Appointment {self.appointment_id}: {self.patient} with {self.therapist}"
        )

    def save(self, *args, **kwargs):
        if not self.appointment_id:
            # Generate a unique appointment ID
            self.appointment_id = f"APT-{get_random_string(6).upper()}"

        # Generate video session link if confirmed and not already set
        if self.status == "confirmed" and not self.video_session_link:
            self.video_session_link = (
                f"https://meet.mindcare.ai/{str(uuid.uuid4())[:8]}"
            )

        if not self.pk:  # New appointment
            self.original_date = self.appointment_date
            self.rescheduled_by = None  # Explicitly set to None for new appointments

            # Skip validation for new appointments to avoid rescheduled_by validation issues
            kwargs["force_insert"] = True
            super().save(*args, **kwargs)
        else:
            # Only run validation for existing appointments
            self.full_clean()
            super().save(*args, **kwargs)

    def clean(self):
        if not self.pk:  # Only for new appointments
            self._validate_future_date()
            self._validate_business_hours()
            self._validate_availability()
            self._validate_concurrent_appointments()
            return  # Skip other validations for new appointments

        if self.appointment_date and self.appointment_date < timezone.now():
            raise ValidationError("Appointment date cannot be in the past")

        # Ensure buffer time between appointments
        buffer_time = timedelta(minutes=15)  # 15-minute buffer between appointments

        # Check for overlapping appointments including buffer time
        overlapping = Appointment.objects.filter(
            models.Q(therapist=self.therapist) | models.Q(patient=self.patient),
            status__in=["scheduled", "confirmed"],
            appointment_date__range=(
                self.appointment_date - buffer_time,
                self.appointment_date + self.duration + buffer_time,
            ),
        )

        if self.pk:  # Exclude current appointment when updating
            overlapping = overlapping.exclude(pk=self.pk)
            # Only validate rescheduled_by for rescheduled appointments
            if self.status == "rescheduled" and not self.rescheduled_by:
                raise ValidationError(
                    {
                        "rescheduled_by": "This field is required when rescheduling an appointment."
                    }
                )

        if overlapping.exists():
            raise ValidationError(
                "This time slot conflicts with another appointment including buffer time"
            )

    def _validate_future_date(self):
        """Ensure appointment is in the future"""
        if self.appointment_date <= timezone.now():
            raise ValidationError("Appointment must be in the future")

    def _validate_business_hours(self):
        """Ensure appointment is during business hours"""
        hour = self.appointment_date.hour
        if not (9 <= hour < 17):  # 9 AM to 5 PM
            raise ValidationError("Appointments must be between 9 AM and 5 PM")

    def _validate_availability(self):
        """Check therapist availability"""
        if not self.therapist.check_availability(
            self.appointment_date, self.duration.total_seconds() / 60
        ):
            raise ValidationError("Therapist is not available at this time")

    def _validate_concurrent_appointments(self):
        """Ensure no overlapping appointments"""
        end_time = self.appointment_date + self.duration
        conflicting = Appointment.objects.filter(
            models.Q(therapist=self.therapist) | models.Q(patient=self.patient),
            appointment_date__lt=end_time,
            status__in=["pending", "confirmed"],
        ).exclude(pk=self.pk)

        for appt in conflicting:
            if appt.appointment_date + appt.duration > self.appointment_date:
                raise ValidationError(
                    "This time slot conflicts with another appointment"
                )

    @property
    def is_upcoming(self):
        """Check if appointment is in the future"""
        return self.appointment_date > timezone.now()

    @property
    def is_past(self):
        """Check if appointment is in the past"""
        return self.appointment_date <= timezone.now()


class WaitingListEntry(models.Model):
    patient = models.ForeignKey(
        "patient.PatientProfile",
        on_delete=models.CASCADE,
        related_name="waiting_list_entries",
    )
    therapist = models.ForeignKey(
        "therapist.TherapistProfile",
        on_delete=models.CASCADE,
        related_name="waiting_list_entries",
    )
    requested_date = models.DateField()
    preferred_time_slots = models.JSONField(
        help_text="List of preferred time slots in HH:MM format"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("notified", "Notified"),
            ("booked", "Booked"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["requested_date", "created_at"]
        indexes = [
            models.Index(fields=["requested_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["therapist", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:  # New entry
            # Set expiration to 48 hours after the requested date
            self.expires_at = timezone.make_aware(
                datetime.combine(self.requested_date, time.max)
            ) + timedelta(days=2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Waiting list entry for {self.patient} with {self.therapist} on {self.requested_date}"


@receiver(post_save, sender=Appointment)
def create_or_use_chat_conversation(sender, instance, created, **kwargs):
    # Check if the appointment is confirmed (either on creation or update)
    if instance.status == "confirmed":
        patient_user = instance.patient.user
        therapist_user = instance.therapist.user
        conversation = (
            OneToOneConversation.objects.filter(participants=patient_user)
            .filter(participants=therapist_user)
            .first()
        )
        if not conversation:
            conversation = OneToOneConversation.objects.create()
            conversation.participants.add(patient_user, therapist_user)
            # Mark that a new conversation was created
            instance.conversation_created = True
        else:
            instance.conversation_created = False

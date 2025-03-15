# therapist/models.py
from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.core.exceptions import ValidationError
from django.utils import timezone
from users.models import CustomUser
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    therapist = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='therapist_appointments',
        limit_choices_to={'user_type': 'therapist'}
    )
    patient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='patient_appointments',
        limit_choices_to={'user_type': 'patient'}
    )
    date_time = models.DateTimeField()
    duration = models.IntegerField(
        default=60,
        validators=[MinValueValidator(15), MaxValueValidator(180)],
        help_text="Duration in minutes (15-180)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_time']
        indexes = [
            models.Index(fields=['therapist', 'date_time']),
            models.Index(fields=['patient', 'date_time']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(date_time__gt=timezone.now()),
                name='appointment_future_date'
            )
        ]

    def __str__(self):
        return f"{self.therapist.username} - {self.patient.username} ({self.date_time})"

    def clean(self):
        if self.date_time <= timezone.now():
            raise ValidationError("Appointment time must be in the future")
        
        # Check for conflicting appointments
        conflicts = Appointment.objects.filter(
            therapist=self.therapist,
            date_time__range=(
                self.date_time,
                self.date_time + timedelta(minutes=self.duration)
            ),
            status__in=['scheduled', 'confirmed']
        ).exclude(pk=self.pk)
        
        if conflicts.exists():
            raise ValidationError("This time slot is already booked")

        # Verify therapist availability
        therapist_profile = TherapistProfile.objects.get(user=self.therapist)
        if not therapist_profile.check_availability(self.date_time, self.duration):
            raise ValidationError("Therapist is not available at this time")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TherapistProfile(models.Model):
    # Basic information - required
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="therapist_profile",
    )

    # Core professional details
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

    # Optional profile details
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(
        upload_to="therapist_profile_pics/", null=True, blank=True
    )

    # Professional fields
    treatment_approaches = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Therapy methods and approaches used",
    )
    available_days = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Weekly availability schedule"
    )
    license_expiry = models.DateField(blank=True, null=True)
    video_session_link = models.URLField(blank=True, null=True)
    languages_spoken = models.JSONField(
        default=list,
        blank=True,
        help_text="Languages the therapist can conduct sessions in",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Profile completion status
    is_profile_complete = models.BooleanField(default=False)
    profile_completion_percentage = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Verification fields
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
        verbose_name = "Therapist Profile"
        verbose_name_plural = "Therapist Profiles"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['specialization']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return f"{self.user.username}'s therapist profile"

    def clean(self):
        """Validate model fields"""
        super().clean()
        
        if self.license_expiry and self.license_expiry < timezone.now().date():
            raise ValidationError(
                {"license_expiry": "License expiry date cannot be in the past"}
            )

        if self.years_of_experience < 0:
            raise ValidationError(
                {"years_of_experience": "Years of experience cannot be negative"}
            )

        # Validate available_days format
        if self.available_days:
            try:
                valid_days = {"monday", "tuesday", "wednesday", "thursday", 
                             "friday", "saturday", "sunday"}
                for day, slots in self.available_days.items():
                    if day.lower() not in valid_days:
                        raise ValidationError(f"Invalid day: {day}")
                    
                    if not isinstance(slots, list):
                        raise ValidationError(f"Schedule for {day} must be a list")
                    
                    for slot in slots:
                        if not isinstance(slot, dict) or "start" not in slot or "end" not in slot:
                            raise ValidationError(f"Invalid time slot format in {day}")
                        
                        # Validate time format
                        try:
                            datetime.strptime(slot['start'], '%H:%M')
                            datetime.strptime(slot['end'], '%H:%M')
                        except ValueError:
                            raise ValidationError(f"Invalid time format in {day}. Use HH:MM format")
            except AttributeError:
                raise ValidationError("available_days must be a dictionary")
            except Exception as e:
                raise ValidationError(f"Invalid available_days format: {str(e)}")

    def save(self, *args, **kwargs):
        self.clean()
        self._calculate_profile_completion()
        super().save(*args, **kwargs)

    def _calculate_profile_completion(self):
        """Calculate profile completion percentage based on essential fields"""
        field_weights = {
            'specialization': 2,
            'license_number': 2,
            'bio': 1,
            'profile_pic': 1,
            'treatment_approaches': 1,
            'available_days': 2,
            'license_expiry': 2,
            'video_session_link': 1,
            'languages_spoken': 1,
        }

        total_weight = sum(field_weights.values())
        weighted_score = 0

        for field, weight in field_weights.items():
            if getattr(self, field):
                weighted_score += weight

        self.profile_completion_percentage = int((weighted_score / total_weight) * 100)
        self.is_profile_complete = self.profile_completion_percentage >= 80

    def check_availability(self, date_time, duration=60):
        """Check if therapist is available at the given time"""
        if not self.available_days:
            return False

        # Get day of week from datetime
        day = date_time.strftime("%A").lower()
        
        # Check if day is in available days
        if day not in self.available_days:
            return False
        
        # Convert datetime to time for comparison
        time = date_time.time()
        end_time = (date_time + timedelta(minutes=duration)).time()
        
        # Check each available slot
        for slot in self.available_days[day]:
            slot_start = datetime.strptime(slot['start'], '%H:%M').time()
            slot_end = datetime.strptime(slot['end'], '%H:%M').time()
            
            if slot_start <= time and end_time <= slot_end:
                # Check for existing appointments
                conflicting_appointments = Appointment.objects.filter(
                    therapist=self.user,
                    date_time__range=(
                        date_time,
                        date_time + timedelta(minutes=duration)
                    ),
                    status__in=['scheduled', 'confirmed']
                ).exists()
                
                return not conflicting_appointments
                
        return False


class AvailableDay(models.Model):
    therapist = models.ForeignKey(TherapistProfile, on_delete=models.CASCADE)
    day = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()


class SessionNote(models.Model):
    therapist = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="therapist_session_notes",
        limit_choices_to={"user_type": "therapist"},
    )
    patient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="patient_session_notes",
        limit_choices_to={"user_type": "patient"},
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="session_note",
        null=True,
        blank=True
    )
    notes = models.TextField()
    session_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the therapy session occurred"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-session_date", "-timestamp"]
        indexes = [
            models.Index(fields=["-session_date"]),
            models.Index(fields=["therapist", "patient"]),
        ]

    def __str__(self):
        return f"Session note for {self.patient.username} by {self.therapist.username}"

    def clean(self):
        if self.appointment and self.session_date != self.appointment.date_time.date():
            raise ValidationError("Session date must match appointment date")


class ClientFeedback(models.Model):
    RATING_CHOICES = [
        (1, "1 - Poor"),
        (2, "2 - Fair"),
        (3, "3 - Good"),
        (4, "4 - Very Good"),
        (5, "5 - Excellent"),
    ]

    therapist = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="therapist_feedback_received",
        limit_choices_to={"user_type": "therapist"},
    )
    patient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="patient_feedback_given",
        limit_choices_to={"user_type": "patient"},
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="feedback",
        null=True,
        blank=True
    )
    feedback = models.TextField(
        help_text="Provide detailed feedback about your session"
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["therapist", "rating"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "therapist", "appointment"],
                name="unique_appointment_feedback",
            )
        ]

    def __str__(self):
        return f"Feedback for {self.therapist.username} from {self.patient.username}"

    def clean(self):
        if self.appointment:
            if self.therapist != self.appointment.therapist:
                raise ValidationError("Feedback therapist must match appointment therapist")
            if self.patient != self.appointment.patient:
                raise ValidationError("Feedback patient must match appointment patient")

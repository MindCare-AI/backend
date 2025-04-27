# therapist/models/client_feedback.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class ClientFeedback(models.Model):
    RATING_CHOICES = [
        (1, "1 - Poor"),
        (2, "2 - Fair"),
        (3, "3 - Good"),
        (4, "4 - Very Good"),
        (5, "5 - Excellent"),
    ]

    therapist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapist_feedback_received",
        limit_choices_to={"user_type": "therapist"},
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_feedback_given",
        limit_choices_to={"user_type": "patient"},
    )
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="feedback",
        null=True,
        blank=True,
    )
    feedback = models.TextField(
        help_text="Provide detailed feedback about your session"
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)]
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
            if self.therapist != self.appointment.therapist.user:
                raise ValidationError(
                    "Feedback therapist must match appointment therapist"
                )
            if self.patient != self.appointment.patient.user:
                raise ValidationError("Feedback patient must match appointment patient")

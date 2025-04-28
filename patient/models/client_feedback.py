# patient/models/client_feedback.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class ClientFeedback(models.Model):
    """Model for client feedback on therapy sessions"""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_given",
    )
    therapist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_received",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="patient_feedback",  # Changed from "feedback"
        null=True,
        blank=True,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback from {self.patient} for {self.therapist}"

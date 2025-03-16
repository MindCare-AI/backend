# therapist/models/session_note.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class SessionNote(models.Model):
    therapist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapist_session_notes",
        limit_choices_to={"user_type": "therapist"},
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_session_notes",
        limit_choices_to={"user_type": "patient"},
    )
    appointment = models.OneToOneField(
        "Appointment",
        on_delete=models.CASCADE,
        related_name="session_note",
        null=True,
        blank=True,
    )
    notes = models.TextField()
    session_date = models.DateField(
        null=True, blank=True, help_text="Date when the therapy session occurred"
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

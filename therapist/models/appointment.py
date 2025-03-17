# therapist/models/appointment.py
import uuid
from django.db import models
from django.utils import timezone
from rest_framework import serializers


class Appointment(models.Model):
    id = models.AutoField(primary_key=True)
    appointment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    therapist = models.ForeignKey(
        "therapist.TherapistProfile",
        on_delete=models.CASCADE,
        related_name="therapist_appointments",  # ✅ Unique name
    )
    patient = models.ForeignKey(
        "patient.PatientProfile",
        on_delete=models.CASCADE,
        related_name="patient_appointments",  # ✅ Unique name
    )
    appointment_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("scheduled", "Scheduled"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
    )
    notes = models.TextField(blank=True)
    duration = models.DurationField(null=True, blank=True)

    class Meta:
        db_table = "therapist_appointment"
        constraints = [
            models.CheckConstraint(
                check=models.Q(appointment_date__gt=models.F("created_at")),
                name="appointment_future_date_check",
            )
        ]
        indexes = [
            models.Index(fields=["therapist", "appointment_date"]),
            models.Index(fields=["patient", "appointment_date"]),
        ]

    def __str__(self):
        return f"Appointment {self.appointment_id} with {self.therapist}"

    def clean(self):
        if self.appointment_date and self.appointment_date <= timezone.now():
            raise models.ValidationError(
                {"appointment_date": "Appointment date must be in the future"}
            )


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "therapist",
            "appointment_date",
            "status",
            "notes",
            "duration",
        ]

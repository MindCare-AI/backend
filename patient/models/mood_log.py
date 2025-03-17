# patient/models/mood_log.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from patient.models.patient_profile import PatientProfile


class MoodLog(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name="mood_logs"
    )
    mood_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    notes = models.TextField(blank=True)
    logged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-logged_at"]
        indexes = [models.Index(fields=["patient", "logged_at"])]

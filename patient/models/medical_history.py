# patient/models/medical_history.py
from django.db import models
from .patient_profile import PatientProfile


class MedicalHistoryEntry(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name="medical_history_entries"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    date_occurred = models.DateField()
    is_chronic = models.BooleanField(default=False)

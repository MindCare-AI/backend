# patient/models/health_metric.py
from django.db import models
from .patient_profile import PatientProfile


class HealthMetric(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name="health_metrics"
    )
    metric_type = models.CharField(
        max_length=20,
        choices=[
            ("blood_pressure", "Blood Pressure"),
            ("weight", "Weight"),
            ("heart_rate", "Heart Rate"),
        ],
    )
    value = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)

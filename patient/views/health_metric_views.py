# patient/views/health_metric_views.py
from rest_framework import viewsets
from rest_framework import permissions
from patient.models.health_metric import HealthMetric
from patient.serializers.health_metric import HealthMetricSerializer
from patient.models.patient_profile import PatientProfile
from rest_framework.exceptions import ValidationError


class HealthMetricViewSet(viewsets.ModelViewSet):
    serializer_class = HealthMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return HealthMetric.objects.filter(patient__user=self.request.user)

    def perform_create(self, serializer):
        try:
            patient = PatientProfile.objects.get(user=self.request.user)
        except PatientProfile.DoesNotExist:
            raise ValidationError("Patient profile not found.")
        serializer.save(patient=patient)

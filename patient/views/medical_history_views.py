# patient/views/medical_history_views.py
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from patient.models.medical_history import MedicalHistoryEntry
from patient.serializers.medical_history import MedicalHistorySerializer


class MedicalHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = MedicalHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MedicalHistoryEntry.objects.filter(patient__user=self.request.user)

    def perform_create(self, serializer):
        if not hasattr(self.request.user, "patientprofile"):
            raise ValidationError(
                "Patient profile not found. Please create one before recording medical history."
            )
        serializer.save(patient=self.request.user.patientprofile)

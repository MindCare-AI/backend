# patient/views/mood_log_views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from patient.models.mood_log import MoodLog
from patient.models.patient_profile import PatientProfile
from patient.serializers.mood_log import MoodLogSerializer
from rest_framework.exceptions import ValidationError


@extend_schema_view(
    list=extend_schema(
        description="List mood log entries for the authenticated patient.",
        summary="List Mood Logs",
        tags=["Mood Log"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific mood log entry.",
        summary="Retrieve Mood Log",
        tags=["Mood Log"],
    ),
    create=extend_schema(
        description="Create a new mood log entry for the patient.",
        summary="Create Mood Log",
        tags=["Mood Log"],
    ),
)
class MoodLogViewSet(viewsets.ModelViewSet):
    serializer_class = MoodLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MoodLog.objects.filter(patient__user=self.request.user)

    def perform_create(self, serializer):
        try:
            patient = PatientProfile.objects.get(user=self.request.user)
        except PatientProfile.DoesNotExist:
            raise ValidationError(
                "Patient profile not found. Please create one before logging a mood."
            )
        serializer.save(patient=patient)

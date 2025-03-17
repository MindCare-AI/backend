# patient/serializers/mood_log.py
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from patient.models.mood_log import MoodLog


class MoodLogSerializer(serializers.ModelSerializer):
    patient_username = serializers.SerializerMethodField()

    class Meta:
        model = MoodLog
        fields = [
            "id",
            "patient",
            "patient_username",
            "mood_rating",
            "notes",
            "logged_at",
        ]
        read_only_fields = ["patient", "logged_at"]

    @extend_schema_field(serializers.CharField)  # Or the appropriate type
    def get_patient_username(self, obj) -> str:  # Add type hint
        return obj.patient.user.username if obj.patient and obj.patient.user else None

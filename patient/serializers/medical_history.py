# patient/serializers/medical_history.py
from rest_framework import serializers
from patient.models.medical_history import MedicalHistoryEntry


class MedicalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalHistoryEntry
        fields = "__all__"
        read_only_fields = ["patient"]

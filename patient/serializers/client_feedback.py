# patient/serializers/client_feedback.py
from rest_framework import serializers
from patient.models.client_feedback import ClientFeedback


class ClientFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for client feedback"""

    class Meta:
        model = ClientFeedback
        fields = [
            "id",
            "patient",
            "therapist",
            "appointment",
            "rating",
            "comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "patient", "created_at", "updated_at"]

    def create(self, validated_data):
        """Set the patient to the current user"""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["patient"] = request.user
        return super().create(validated_data)

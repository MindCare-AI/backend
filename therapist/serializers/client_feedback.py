# therapist/serializers/client_feedback.py
from rest_framework import serializers
from therapist.models.client_feedback import ClientFeedback


class ClientFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientFeedback
        fields = ["id", "therapist", "patient", "feedback", "rating", "timestamp"]

# therapist/serializers.py
from rest_framework import serializers
from .models import TherapistProfile, SessionNote, ClientFeedback


class TherapistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "specialization",
            "license_number",
            "years_of_experience",
            "bio",
            "profile_pic",
        ]


class SessionNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ["id", "therapist", "patient", "notes", "timestamp"]


class ClientFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientFeedback
        fields = ["id", "therapist", "patient", "feedback", "rating", "timestamp"]

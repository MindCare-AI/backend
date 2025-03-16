# therapist/serializers/session_note.py
from rest_framework import serializers
from therapist.models.session_note import SessionNote


class SessionNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ["id", "therapist", "patient", "notes", "timestamp"]

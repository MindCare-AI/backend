# therapist/serializers/session_note.py
from rest_framework import serializers
from therapist.models.session_note import SessionNote
from datetime import datetime


class SessionNoteSerializer(serializers.ModelSerializer):
    """Serializer for therapy session notes"""

    class Meta:
        model = SessionNote
        fields = [
            "id",
            "therapist",
            "patient",
            "appointment",
            "notes",
            "session_date",
            "timestamp",
            "updated_at",
        ]
        read_only_fields = ["id", "therapist", "timestamp", "updated_at"]

    def validate(self, attrs):
        """Validate the session note data"""
        if attrs.get("appointment"):
            # Validate session date matches appointment date
            if (
                attrs.get("session_date")
                and attrs["session_date"]
                != attrs["appointment"].appointment_date.date()
            ):
                raise serializers.ValidationError(
                    "Session date must match appointment date"
                )

            # Set session date from appointment if not provided
            if not attrs.get("session_date"):
                attrs["session_date"] = attrs["appointment"].appointment_date.date()

            # Allow future dates if they match the appointment date
            # Otherwise check that the session date isn't in the future
        elif (
            attrs.get("session_date") and attrs["session_date"] > datetime.now().date()
        ):
            raise serializers.ValidationError("Session date cannot be in the future")

        return attrs

    def create(self, validated_data):
        """Set the therapist when creating a note"""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            # Set therapist to the user, not therapist_profile
            validated_data["therapist"] = request.user
        return super().create(validated_data)

# therapist/serializers/availability.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile
from datetime import datetime
import json


class DayTimeSlotField(serializers.DictField):
    """Custom field for validating and displaying daily time slots"""

    def to_internal_value(self, data):
        # If the input data is a JSON string, parse it into a dict.
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                raise serializers.ValidationError("Invalid JSON input")

        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "Available days must be provided as a dictionary"
            )

        valid_days = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        validated_data = {}

        for day, slots in data.items():
            day_lower = day.lower()
            if day_lower not in valid_days:
                raise serializers.ValidationError(f"Invalid day: {day}")

            if not isinstance(slots, list):
                raise serializers.ValidationError(f"Schedule for {day} must be a list")

            validated_slots = []
            for slot in slots:
                if (
                    not isinstance(slot, dict)
                    or "start" not in slot
                    or "end" not in slot
                ):
                    raise serializers.ValidationError(
                        f"Invalid time slot format in {day}. Expected {{'start': 'HH:MM', 'end': 'HH:MM'}}"
                    )
                try:
                    start_time = datetime.strptime(slot["start"], "%H:%M").time()
                    end_time = datetime.strptime(slot["end"], "%H:%M").time()
                    if start_time >= end_time:
                        raise serializers.ValidationError(
                            f"Start time must be before end time in {day} slot {slot}"
                        )
                    validated_slots.append({"start": slot["start"], "end": slot["end"]})
                except ValueError:
                    raise serializers.ValidationError(
                        f"Invalid time format in {day}. Use HH:MM format"
                    )
            validated_data[day_lower] = validated_slots

        return validated_data

    def to_representation(self, value):
        """Return the value as a proper dictionary for output"""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {}
        return value or {}


class TherapistAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for therapist availability information only"""

    available_days = DayTimeSlotField(
        required=True,
        style={
            "base_template": "textarea.html",
            "input_type": "text",
            "rows": 10,
            "cols": 50,
        },
        help_text="Enter available days as JSON. Example: { 'monday': [{'start': '09:00', 'end': '17:00'}], 'tuesday': [...] }",
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "available_days",
            "video_session_link",
        ]

    def to_internal_value(self, data):
        """Custom parsing for the raw data field"""
        if (
            isinstance(data, dict)
            and "available_days" in data
            and isinstance(data["available_days"], str)
        ):
            try:
                data = data.copy()  # Create a mutable copy
                data["available_days"] = json.loads(data["available_days"])
            except json.JSONDecodeError:
                pass  # Let the field validation handle this
        return super().to_internal_value(data)

    def to_representation(self, instance):
        """Pre-populate the form with the current values"""
        ret = super().to_representation(instance)
        return ret

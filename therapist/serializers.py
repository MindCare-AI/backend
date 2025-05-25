# therapist/serializers.py
from rest_framework import serializers
from therapist.models import TherapistProfile, Availability


class TherapistProfilePublicSerializer(serializers.ModelSerializer):
    availability = serializers.SerializerMethodField()

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "specialization",
            "experience",
            "availability",
        ]

    def get_availability(self, obj):
        # Only include availability if requested in context
        if not self.context.get("include_availability", False):
            return None

        # Get the therapist's availability
        availability_data = obj.availability_set.all()

        # Use AvailabilitySerializer to serialize availability data
        return AvailabilitySerializer(availability_data, many=True).data


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ["day", "start_time", "end_time"]

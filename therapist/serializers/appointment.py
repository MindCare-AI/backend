# therapist/serializers/appointment.py
from rest_framework import serializers
from therapist.models.appointment import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "therapist",
            "appointment_date",
            "status",
            "notes",
            "duration",
        ]

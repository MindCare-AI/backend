# therapist/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import TherapistProfile, SessionNote, ClientFeedback, Appointment
from users.models import CustomUser


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)

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
            "treatment_approaches",
            "available_days",
            "license_expiry",
            "video_session_link",
            "languages_spoken",
            "profile_completion_percentage",
            "is_profile_complete",
            "created_at",
            "updated_at",
            "verification_status",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
            "profile_completion_percentage",
            "is_profile_complete",
        ]


class SessionNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ["id", "therapist", "patient", "notes", "timestamp"]


class ClientFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientFeedback
        fields = ["id", "therapist", "patient", "feedback", "rating", "timestamp"]


class AppointmentSerializer(serializers.ModelSerializer):
    therapist_name = serializers.CharField(source='therapist.username', read_only=True)
    patient_name = serializers.CharField(source='patient.username', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "therapist",
            "therapist_name",
            "patient",
            "patient_name",
            "date_time",
            "duration",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        # Ensure appointment time is in the future
        if data.get('date_time') and data['date_time'] <= timezone.now():
            raise serializers.ValidationError({
                "date_time": "Appointment time must be in the future"
            })

        # Check if the therapist is available at this time
        if self.instance is None:  # Only check on create
            conflicting_appointments = Appointment.objects.filter(
                therapist=data['therapist'],
                date_time__range=(
                    data['date_time'],
                    data['date_time'] + timezone.timedelta(minutes=data.get('duration', 60))
                ),
                status__in=['scheduled', 'confirmed']
            )
            if conflicting_appointments.exists():
                raise serializers.ValidationError({
                    "date_time": "This time slot is already booked"
                })

        return data

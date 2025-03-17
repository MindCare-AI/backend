# therapist/serializers/appointment.py
from rest_framework import serializers
from therapist.models.appointment import Appointment
from therapist.models.therapist_profile import TherapistProfile

from django.utils import timezone
from datetime import timedelta
from django.db.models import ExpressionWrapper, F, DateTimeField


class AppointmentSerializer(serializers.ModelSerializer):
    therapist_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    duration_minutes = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "therapist",
            "therapist_name",
            "patient",
            "patient_name",
            "appointment_date",  # Updated to match the model field name
            "duration",
            "duration_minutes",
            "status",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "duration"]
        extra_kwargs = {
            'duration': {'read_only': True}
        }

    def get_therapist_name(self, obj):
        return obj.therapist.user.username  # Access username through TherapistProfile -> User

    def get_patient_name(self, obj):
        return obj.patient.user.username  # Access username through PatientProfile -> User

    def validate(self, data):
        status = data.get("status", getattr(self.instance, "status", "scheduled"))
        therapist = data.get("therapist", getattr(self.instance, "therapist", None))
        appointment_date = data.get("appointment_date", getattr(self.instance, "appointment_date", None))
        duration_minutes = data.get('duration_minutes', 60)
        
        if not all([therapist, appointment_date]):
            raise serializers.ValidationError(
                {"error": "Therapist and appointment_date are required fields"}
            )

        if status in ["scheduled", "confirmed"]:
            if appointment_date <= timezone.now():
                raise serializers.ValidationError(
                    {
                        "appointment_date": "Appointment time must be in the future for scheduled or confirmed status",
                        "current_time": timezone.now().isoformat(),
                    }
                )

            new_end = appointment_date + timedelta(minutes=duration_minutes)
            
            conflicts = Appointment.objects.annotate(
                existing_end=ExpressionWrapper(
                    F("appointment_date") + F("duration"),
                    output_field=DateTimeField(),
                )
            ).filter(
                therapist=therapist,
                status__in=["scheduled", "confirmed"],
                appointment_date__lt=new_end,
                existing_end__gt=appointment_date,
            )

            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)

            if conflicts.exists():
                raise serializers.ValidationError(
                    {
                        "appointment_date": "This time slot overlaps with existing appointments",
                        "conflicts": [
                            {
                                "time": c.appointment_date.strftime("%Y-%m-%d %H:%M"),
                                "duration": c.duration,
                                "status": c.status,
                            }
                            for c in conflicts[:3]
                        ],
                    }
                )

            try:
                therapist_profile = TherapistProfile.objects.get(user=therapist.user)
                if not therapist_profile.is_verified:
                    raise serializers.ValidationError(
                        {"therapist": "Therapist's profile is not verified"}
                    )

                # Pass duration_minutes directly instead of converting to timedelta
                if not therapist_profile.check_availability(appointment_date, duration_minutes):
                    available_slots = therapist_profile.available_days.get(
                        appointment_date.strftime("%A").lower(), []
                    )
                    raise serializers.ValidationError(
                        {
                            "appointment_date": "Therapist is not available at this time",
                            "available_slots": [
                                f"{slot['start']} - {slot['end']}"
                                for slot in available_slots
                            ],
                        }
                    )

            except TherapistProfile.DoesNotExist:
                raise serializers.ValidationError(
                    {"therapist": "Therapist profile does not exist"}
                )

        if duration_minutes < 1:
            raise serializers.ValidationError({"duration_minutes": "Duration must be at least 1 minute."})
        data['duration'] = timedelta(minutes=duration_minutes)

        return data

    def create(self, validated_data):
        validated_data.pop('duration_minutes', None)  # Handled in validate
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('duration_minutes', None)
        return super().update(instance, validated_data)

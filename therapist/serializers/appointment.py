# therapist/serializers/appointment.py
from rest_framework import serializers
from therapist.models.appointment import Appointment
from therapist.models.therapist_profile import TherapistProfile

from django.utils import timezone
from datetime import timedelta
from django.db.models import ExpressionWrapper, F, DateTimeField


class AppointmentSerializer(serializers.ModelSerializer):
    therapist_name = serializers.CharField(source="therapist.username", read_only=True)
    patient_name = serializers.CharField(source="patient.username", read_only=True)

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
        status = data.get("status", getattr(self.instance, "status", "scheduled"))

        therapist = data.get("therapist", getattr(self.instance, "therapist", None))
        date_time = data.get("date_time", getattr(self.instance, "date_time", None))
        duration = data.get("duration", getattr(self.instance, "duration", 60))

        if not all([therapist, date_time]):
            raise serializers.ValidationError(
                {"error": "Therapist and date_time are required fields"}
            )

        if status in ["scheduled", "confirmed"]:
            if date_time <= timezone.now():
                raise serializers.ValidationError(
                    {
                        "date_time": "Appointment time must be in the future for scheduled or confirmed status",
                        "current_time": timezone.now().isoformat(),
                    }
                )

            new_end = date_time + timedelta(minutes=duration)

            conflicts = Appointment.objects.annotate(
                existing_end=ExpressionWrapper(
                    F("date_time") + F("duration") * timedelta(minutes=1),
                    output_field=DateTimeField(),
                )
            ).filter(
                therapist=therapist,
                status__in=["scheduled", "confirmed"],
                date_time__lt=new_end,
                existing_end__gt=date_time,
            )

            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)

            if conflicts.exists():
                raise serializers.ValidationError(
                    {
                        "date_time": "This time slot overlaps with existing appointments",
                        "conflicts": [
                            {
                                "time": c.date_time.strftime("%Y-%m-%d %H:%M"),
                                "duration": c.duration,
                                "status": c.status,
                            }
                            for c in conflicts[:3]
                        ],
                    }
                )

            try:
                therapist_profile = TherapistProfile.objects.get(user=therapist)

                if not therapist_profile.is_verified:
                    raise serializers.ValidationError(
                        {"therapist": "Therapist's profile is not verified"}
                    )

                if not therapist_profile.check_availability(date_time, duration):
                    available_slots = therapist_profile.available_days.get(
                        date_time.strftime("%A").lower(), []
                    )
                    raise serializers.ValidationError(
                        {
                            "date_time": "Therapist is not available at this time",
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

        return data

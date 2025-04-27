from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Appointment, WaitingListEntry


class AppointmentSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(
        write_only=True, required=False, default=60
    )
    therapist_name = serializers.CharField(
        source="therapist.user.get_full_name", read_only=True
    )
    patient_name = serializers.CharField(
        source="patient.user.get_full_name", read_only=True
    )
    is_upcoming = serializers.BooleanField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    can_cancel = serializers.SerializerMethodField()
    can_confirm = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()
    rescheduled_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "appointment_id",
            "patient",
            "therapist",
            "therapist_name",
            "patient_name",
            "appointment_date",
            "status",
            "notes",
            "duration_minutes",
            "duration",
            "created_at",
            "updated_at",
            "is_upcoming",
            "is_past",
            "can_cancel",
            "can_confirm",
            "can_complete",
            "video_session_link",
            "cancelled_by",
            "cancelled_by_name",
            "cancellation_reason",
            "reminder_sent",
            "original_date",
            "reschedule_count",
            "last_rescheduled",
            "rescheduled_by",
            "rescheduled_by_name",
        ]
        read_only_fields = [
            "appointment_id",
            "created_at",
            "updated_at",
            "video_session_link",
            "reminder_sent",
            "original_date",
            "reschedule_count",
            "last_rescheduled",
        ]

    def get_can_cancel(self, obj):
        # Can cancel if appointment is upcoming and not already cancelled/completed
        return (
            obj.is_upcoming
            and obj.status not in ["cancelled", "completed"]
            and (timezone.now() + timedelta(hours=24)) < obj.appointment_date
        )

    def get_can_confirm(self, obj):
        # Only therapist can confirm pending appointments
        request = self.context.get("request")
        return (
            request
            and request.user.user_type == "therapist"
            and obj.status == "pending"
            and obj.therapist.user == request.user
        )

    def get_can_complete(self, obj):
        # Only therapist can mark appointments as completed
        request = self.context.get("request")
        return (
            request
            and request.user.user_type == "therapist"
            and obj.status == "confirmed"
            and obj.therapist.user == request.user
            and obj.appointment_date < timezone.now()
        )

    def get_rescheduled_by_name(self, obj):
        return obj.rescheduled_by.get_full_name() if obj.rescheduled_by else None

    def get_cancelled_by_name(self, obj):
        return obj.cancelled_by.get_full_name() if obj.cancelled_by else None

    def validate(self, data):
        if self.instance is None:  # Creating new appointment
            if "duration_minutes" in data:
                data["duration"] = timedelta(minutes=data.pop("duration_minutes"))
            elif "duration" not in data:
                data["duration"] = timedelta(minutes=60)  # Default duration

            # Validate appointment date is in future
            if (
                data.get("appointment_date")
                and data["appointment_date"] <= timezone.now()
            ):
                raise serializers.ValidationError(
                    {"appointment_date": "Appointment must be in the future"}
                )

            # Check therapist availability
            if data.get("therapist") and data.get("appointment_date"):
                if not data["therapist"].check_availability(
                    data["appointment_date"], data["duration"].total_seconds() / 60
                ):
                    raise serializers.ValidationError(
                        {"appointment_date": "Therapist is not available at this time"}
                    )

        # Convert duration_minutes to timedelta if provided
        if "duration_minutes" in data:
            data["duration"] = timedelta(minutes=data.pop("duration_minutes"))

        # Validate appointment date
        if "appointment_date" in data:
            min_notice = timezone.now() + timedelta(hours=24)
            if data["appointment_date"] < min_notice:
                raise serializers.ValidationError(
                    "Appointments must be scheduled at least 24 hours in advance"
                )

        return data

    def create(self, validated_data):
        # Ensure original_date is set for new appointments
        validated_data["original_date"] = validated_data.get("appointment_date")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Track rescheduling if appointment date changes
        if (
            "appointment_date" in validated_data
            and validated_data["appointment_date"] != instance.appointment_date
        ):
            validated_data["last_rescheduled"] = timezone.now()
            validated_data["reschedule_count"] = instance.reschedule_count + 1
            validated_data["rescheduled_by"] = self.context["request"].user

        return super().update(instance, validated_data)


class WaitingListEntrySerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(
        source="patient.user.get_full_name", read_only=True
    )
    therapist_name = serializers.CharField(
        source="therapist.user.get_full_name", read_only=True
    )

    class Meta:
        model = WaitingListEntry
        fields = [
            "id",
            "patient",
            "patient_name",
            "therapist",
            "therapist_name",
            "requested_date",
            "preferred_time_slots",
            "notes",
            "status",
            "created_at",
            "notified_at",
            "expires_at",
        ]
        read_only_fields = ["status", "created_at", "notified_at", "expires_at"]

    def validate_preferred_time_slots(self, value):
        """Validate time slots are in correct format and within business hours"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Time slots must be a list")

        for slot in value:
            try:
                time = datetime.strptime(slot, "%H:%M").time()
                if not (9 <= time.hour < 17):
                    raise serializers.ValidationError(
                        f"Time slot {slot} is outside business hours (9 AM - 5 PM)"
                    )
            except ValueError:
                raise serializers.ValidationError(
                    f"Invalid time format for {slot}. Use HH:MM format"
                )

        return value

    def validate_requested_date(self, value):
        """Validate requested date is in the future"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Requested date must be in the future")
        return value

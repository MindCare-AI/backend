from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta, datetime
import re
from .models import Appointment, WaitingListEntry


class AppointmentSerializer(serializers.ModelSerializer):
    # Example: a field that appears in the serializer but is not a model field must be read-only
    # If patient_profile is provided to the serializer you can mark it as read-only:
    patient_profile = serializers.CharField(read_only=True, required=False)

    # Override to use 24-hour format in output
    appointment_date = serializers.DateTimeField(format='%Y-%m-%d %H:%M')
    duration = serializers.CharField(
        help_text="Select the appointment duration in minutes (24-hour time)"
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
            "patient_profile",
            "appointment_date",
            "status",
            "notes",
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
            "rescheduled_by",
        ]
        extra_kwargs = {
            "rescheduled_by": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = getattr(self, "initial_data", None)
        if initial and initial.get("therapist"):
            try:
                from .models import Therapist  # adjust import if necessary
                therapist = Therapist.objects.get(pk=initial.get("therapist"))
                if hasattr(therapist, "get_available_days"):
                    available_days = therapist.get_available_days()  # expected list of date objects
                    self.fields["appointment_date"] = serializers.ChoiceField(
                        choices=[(day.isoformat(), day.strftime("%Y-%m-%d")) for day in available_days],
                        help_text="Select an available day for the appointment"
                    )
            except Exception:
                pass

    def get_can_cancel(self, obj):
        return (
            obj.is_upcoming
            and obj.status not in ["cancelled", "completed"]
            and (timezone.now() + timedelta(hours=24)) < obj.appointment_date
        )

    def get_can_confirm(self, obj):
        request = self.context.get("request")
        return (
            request
            and request.user.user_type == "therapist"
            and obj.status == "pending"
            and obj.therapist.user == request.user
        )

    def get_can_complete(self, obj):
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
            try:
                # First check if appointment_date exists in the data
                if "appointment_date" not in data:
                    raise serializers.ValidationError({"appointment_date": "Please select an appointment day"})
                
                # Parse 'appointment_date' safely - support 24-hour format
                date_str = str(data["appointment_date"]).replace("\u202f", " ").strip()
                
                try:
                    # First try 24-hour format
                    appointment_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        # Try ISO format
                        appointment_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except ValueError:
                        raise serializers.ValidationError(
                            {"appointment_date": "Invalid date format. Use YYYY-MM-DD HH:MM (24-hour format)"}
                        )

                # Store the parsed datetime back in data to avoid re-parsing later
                data["appointment_date"] = appointment_dt
                
                # Validate appointment time
                if appointment_dt < (timezone.now() + timedelta(hours=24)):
                    raise serializers.ValidationError(
                        {"appointment_date": "Appointments need 24-hour notice"}
                    )

                # Convert duration to integer safely
                try:
                    duration_str = data.get('duration', '60')
                    if not duration_str:
                        data['duration'] = 60
                    elif isinstance(duration_str, int):
                        data['duration'] = duration_str
                    else:
                        # Extract digits from string
                        digits = re.sub(r'[^0-9]', '', str(duration_str))
                        data['duration'] = int(digits) if digits else 60
                except (ValueError, TypeError):
                    data['duration'] = 60  # Default to 60 minutes

                # Convert duration to timedelta
                duration = data.get("duration", None)
                if isinstance(duration, int):
                    data["duration"] = timedelta(minutes=duration)
                elif isinstance(duration, str):
                    try:
                        minutes = int(duration)
                        data["duration"] = timedelta(minutes=minutes)
                    except ValueError:
                        data["duration"] = timedelta(minutes=60)

                # Remove any extra fields that are not valid model fields
                data.pop("patient_profile", None)

                # Rest of validation code...
            except KeyError as e:
                raise serializers.ValidationError({str(e): "This field is required"})
                
        else:  # Updating existing appointment
            # Handle update case
            if "appointment_date" in data:
                # Similar parsing as above for update
                pass

            # Convert duration during update as well if it exists
            if "duration" in data:
                duration = data["duration"]
                if isinstance(duration, int):
                    data["duration"] = timedelta(minutes=duration)
                elif isinstance(duration, str):
                    try:
                        minutes = int(duration)
                        data["duration"] = timedelta(minutes=minutes)
                    except ValueError:
                        data["duration"] = timedelta(minutes=60)
        
        return data

    def create(self, validated_data):
        # Remove any extra fields that are not valid model fields
        validated_data.pop("patient_profile", None)
        
        # Explicitly set rescheduled_by to None for new appointments
        validated_data["rescheduled_by"] = None
        
        # Set original_date to appointment_date for new appointments
        validated_data["original_date"] = validated_data.get("appointment_date")
        
        # Convert duration from minutes (int) to timedelta if necessary
        duration = validated_data.get("duration", None)
        if isinstance(duration, int):
            validated_data["duration"] = timedelta(minutes=duration)
        elif isinstance(duration, str):
            try:
                minutes = int(duration)
                validated_data["duration"] = timedelta(minutes=minutes)
            except ValueError:
                validated_data["duration"] = timedelta(minutes=60)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if (
            "appointment_date" in validated_data
            and validated_data["appointment_date"] != instance.appointment_date.isoformat()
        ):
            validated_data["last_rescheduled"] = timezone.now()
            validated_data["reschedule_count"] = instance.reschedule_count + 1
            validated_data["rescheduled_by"] = self.context["request"].user

        validated_data.pop("patient_profile", None)
        # Convert duration during update as well if it exists
        if "duration" in validated_data:
            duration = validated_data["duration"]
            if isinstance(duration, int):
                validated_data["duration"] = timedelta(minutes=duration)
            elif isinstance(duration, str):
                try:
                    minutes = int(duration)
                    validated_data["duration"] = timedelta(minutes=minutes)
                except ValueError:
                    validated_data["duration"] = timedelta(minutes=60)
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
        if value < timezone.now().date():
            raise serializers.ValidationError("Requested date must be in the future")
        return value


class AppointmentConfirmationSerializer(serializers.ModelSerializer):
    appointment_id = serializers.CharField(read_only=True)
    appointment_date = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M')
    patient_name = serializers.CharField(source="patient.user.get_full_name", read_only=True)
    status = serializers.CharField(read_only=True)
    confirmed_by = serializers.SerializerMethodField()
    confirmation_date = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            "appointment_id",
            "appointment_date",
            "patient_name",
            "status",
            "confirmed_by",
            "confirmation_date",
            "video_session_link",
        ]
        read_only_fields = fields
    
    def get_confirmed_by(self, obj):
        request = self.context.get("request")
        if request and request.user:
            return request.user.get_full_name() or request.user.username
        return None
    
    def get_confirmation_date(self, obj):
        return timezone.now()

# therapist/serializers/therapist_profile.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile
from datetime import datetime  # Add datetime import
from django.conf import settings
import magic
from django.utils import timezone

# Real-life specialization choices for therapists
SPECIALIZATION_CHOICES = [
    ("anxiety_disorders", "Anxiety Disorders"),
    ("depressive_disorders", "Depressive Disorders"),
    ("bipolar_disorders", "Bipolar Disorders"),
    ("eating_disorders", "Eating Disorders"),
    ("ocd", "Obsessive-Compulsive Disorders"),
    ("trauma_ptsd", "Trauma and PTSD"),
    ("personality_disorders", "Personality Disorders"),
    ("substance_abuse", "Substance Abuse"),
    ("child_adolescent", "Child & Adolescent Issues"),
    ("relationship_couples", "Relationship/Couples Therapy"),
    ("grief_loss", "Grief and Loss"),
    ("stress_management", "Stress Management"),
    ("life_coaching", "Life Coaching"),
]

TREATMENT_APPROACH_CHOICES = [
    ("CBT", "Cognitive Behavioral Therapy"),
    ("DBT", "Dialectical Behavior Therapy"),
]

LANGUAGE_CHOICES = [
    ("English", "English"),
    ("Spanish", "Spanish"),
    ("French", "French"),
    ("German", "German"),
    ("Chinese", "Chinese"),
    ("Japanese", "Japanese"),
    ("Korean", "Korean"),
    ("Italian", "Italian"),
    ("Portuguese", "Portuguese"),
    ("Russian", "Russian"),
    ("Arabic", "Arabic"),
    # Add any additional languages if needed
]

DAY_CHOICES = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]


class DayTimeSlotField(serializers.DictField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("available_days must be a dictionary.")

        validated_data = {}
        valid_days = {day[0] for day in DAY_CHOICES}

        for day, slots in data.items():
            day_lower = day.lower()
            if day_lower not in valid_days:
                raise serializers.ValidationError(f"Invalid day: {day}")

            if not isinstance(slots, list):
                raise serializers.ValidationError(
                    f"Schedule for {day_lower} must be a list of time slots."
                )

            validated_slots = []
            for slot in slots:
                if (
                    not isinstance(slot, dict)
                    or "start" not in slot
                    or "end" not in slot
                ):
                    raise serializers.ValidationError(
                        f"Invalid time slot format in {day_lower}. Expected {{'start': 'HH:MM', 'end': 'HH:MM'}}."
                    )

                try:
                    start_time = datetime.strptime(slot["start"], "%H:%M").time()
                    end_time = datetime.strptime(slot["end"], "%H:%M").time()
                    if start_time >= end_time:
                        raise serializers.ValidationError(
                            f"Start time must be before end time in {day_lower} for slot {slot}."
                        )
                    validated_slots.append({"start": slot["start"], "end": slot["end"]})
                except ValueError:
                    raise serializers.ValidationError(
                        f"Invalid time format in {day_lower}. Use HH:MM format."
                    )

            validated_data[day_lower] = validated_slots

        return validated_data


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.SerializerMethodField()
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", required=False)

    specializations = serializers.MultipleChoiceField(
        choices=SPECIALIZATION_CHOICES,
        required=False,
        allow_empty=True,
    )
    years_of_experience = serializers.IntegerField(
        min_value=0, max_value=100, required=False
    )
    treatment_approaches = serializers.MultipleChoiceField(
        choices=TREATMENT_APPROACH_CHOICES,
        required=False,
        allow_empty=True,
    )
    languages = serializers.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone_number",
            "bio",
            "specializations",
            "experience",
            "years_of_experience",
            "license_number",
            "license_expiry",
            "profile_picture",
            "treatment_approaches",
            "languages",
            "rating",
            "total_ratings",
            "total_sessions",
            "profile_completion",
            "is_verified",
            "verification_status",
            "hourly_rate",
            "accepts_insurance",
            "insurance_providers",
            "session_duration",
        ]
        read_only_fields = [
            "id",
            "user",
            "email",
            "rating",
            "total_ratings",
            "total_sessions",
            "profile_completion",
            "is_verified",
            "verification_status",
        ]

    def get_username(self, obj):
        return obj.user.username

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        for attr, value in validated_data.items():
            if isinstance(value, set):
                value = list(value)
            setattr(instance, attr, value)
        instance.save()
        return instance


class TherapistVerificationSerializer(serializers.Serializer):
    """Serializer for therapist verification process"""

    license_image = serializers.ImageField(
        required=True,
        help_text="Image of the therapist's license",
        style={"template": "input.html", "type": "file"},
    )
    selfie_image = serializers.ImageField(
        required=True,
        help_text="Current selfie of the therapist for verification",
        style={"template": "input.html", "type": "file"},
    )
    license_number = serializers.CharField(
        required=True,
        max_length=100,
        help_text="License number from the verification document",
        style={"template": "input.html", "type": "text"},
    )
    issuing_authority = serializers.CharField(
        required=True,
        max_length=200,
        help_text="Authority that issued the license",
        style={"template": "input.html", "type": "text"},
    )
    specializations = serializers.MultipleChoiceField(
        choices=SPECIALIZATION_CHOICES,
        required=False,
        allow_empty=True,
        help_text="Areas of specialization",
        style={"template": "checkbox_select.html", "base_template": "input.html"},
    )

    class Meta:
        fields = [
            "license_image",
            "selfie_image",
            "license_number",
            "issuing_authority",
            "specializations",
        ]

    def validate_license_image(self, value):
        """Validate license image file type and size"""
        if (
            value.size
            > settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"]
        ):
            raise serializers.ValidationError("License image file is too large")

        mime_type = magic.from_buffer(value.read(2048), mime=True)
        value.seek(0)  # Reset file pointer after reading

        if (
            mime_type
            not in settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"][
                "ALLOWED_MIME_TYPES"
            ]
        ):
            raise serializers.ValidationError("Invalid file type for license image")

        return value

    def validate_selfie_image(self, value):
        """Validate selfie image file type and size"""
        if (
            value.size
            > settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"]
        ):
            raise serializers.ValidationError("Selfie image file is too large")

        mime_type = magic.from_buffer(value.read(2048), mime=True)
        value.seek(0)  # Reset file pointer after reading

        if (
            mime_type
            not in settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"][
                "ALLOWED_MIME_TYPES"
            ]
        ):
            raise serializers.ValidationError("Invalid file type for selfie image")

        return value


class VerificationStatusSerializer(serializers.ModelSerializer):
    """Serializer for viewing verification status"""

    class Meta:
        model = TherapistProfile
        fields = [
            "is_verified",
            "verification_status",
            "verification_notes",
            "verified_at",
            "verification_expiry",
            "license_number",
            "license_expiry",
            "issuing_authority",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        """Add custom fields to the verification status response"""
        data = super().to_representation(instance)
        data["can_submit"] = not instance.is_verified
        if instance.is_verified:
            data["days_until_expiry"] = (
                (instance.verification_expiry - timezone.now().date()).days
                if instance.verification_expiry
                else None
            )
        return data


class TherapistAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for therapist availability information only"""

    class Meta:
        model = TherapistProfile
        fields = [
            "available_days",
            "video_session_link",
            "languages",
        ]
        read_only_fields = fields


class TherapistProfilePublicSerializer(serializers.ModelSerializer):
    """Serializer for public display of therapist profiles"""

    availability = serializers.SerializerMethodField()
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "profile_picture",
            "bio",
            "specializations",
            "years_of_experience",
            "education",
            "license_number",
            "languages",
            "is_verified",
            "rating",
            "hourly_rate",
            "availability",
        ]

    def get_availability(self, obj):
        # Only include availability if requested in context
        if not self.context.get("include_availability", False):
            return None

        # Get the therapist's availability
        from therapist.serializers.availability import TherapistAvailabilitySerializer

        availability_serializer = TherapistAvailabilitySerializer(obj)
        return availability_serializer.data.get("available_days", {})

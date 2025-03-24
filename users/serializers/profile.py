# users/serializers/profile.py
from rest_framework import serializers
from patient.models.patient_profile import PatientProfile  # Updated import
from therapist.models.therapist_profile import TherapistProfile
from users.validators.user_validators import (
    validate_profile_pic,
    validate_emergency_contact,
    validate_blood_type,
)


class PatientProfileSerializer(serializers.ModelSerializer):
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("N", "Prefer not to say"),
    ]

    profile_pic = serializers.ImageField(
        validators=[validate_profile_pic], required=False
    )
    emergency_contact = serializers.JSONField(
        validators=[validate_emergency_contact], required=False
    )
    blood_type = serializers.CharField(validators=[validate_blood_type], required=False)
    gender = serializers.ChoiceField(choices=GENDER_CHOICES, required=False)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "bio",
            "profile_pic",
            "emergency_contact",
            "medical_history",
            "current_medications",
            "blood_type",
            "treatment_plan",
            "pain_level",
            "gender",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TherapistProfileSerializer(serializers.ModelSerializer):
    AVAILABILITY_STATUS = [
        ("ACTIVE", "Active"),
        ("AWAY", "Away"),
        ("BUSY", "Busy"),
        ("OFFLINE", "Offline"),
    ]

    profile_pic = serializers.ImageField(
        validators=[validate_profile_pic], required=False
    )
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    availability_status = serializers.ChoiceField(
        choices=AVAILABILITY_STATUS, default="ACTIVE"
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "bio",
            "profile_pic",
            "specialization",
            "license_number",
            "years_of_experience",
            "treatment_approaches",
            "available_days",
            "license_expiry",
            "video_session_link",
            "languages_spoken",
            "availability_status",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
        ]

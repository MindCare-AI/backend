# patient/serializers.py
from rest_framework import serializers
from .models import PatientProfile
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class PatientProfileSerializer(serializers.ModelSerializer):
    emergency_contact = serializers.JSONField(required=False)
    blood_type = serializers.CharField(max_length=3, required=False, allow_null=True)
    pain_level = serializers.IntegerField(
        min_value=0, max_value=10, required=False, allow_null=True
    )
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "user",
            "user_name",
            "medical_history",
            "current_medications",
            "profile_pic",
            "blood_type",
            "emergency_contact",
            "treatment_plan",
            "pain_level",
            "last_appointment",
            "next_appointment",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    def validate_emergency_contact(self, value):
        """
        Validate emergency contact information contains required fields
        """
        required_fields = ["name", "relationship", "phone"]
        if value and not all(field in value for field in required_fields):
            raise ValidationError(
                f"Emergency contact must include: {', '.join(required_fields)}"
            )
        
        # Validate phone number format
        if value and not value['phone'].replace('+', '').isdigit():
            raise ValidationError("Phone number must contain only digits and optional +")
            
        return value

    def validate_blood_type(self, value):
        """
        Validate blood type is in correct format
        """
        valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        if value and value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid blood type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate_profile_pic(self, value):
        """
        Validate profile picture size and format
        """
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError("Image file too large ( > 5MB )")

            if not value.content_type.startswith("image/"):
                raise serializers.ValidationError("File must be an image")
        return value


from .models import MoodLog  # import the MoodLog model


class MoodLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodLog
        fields = ["id", "user", "mood", "timestamp"]

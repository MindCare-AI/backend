# patient/serializers.py
from rest_framework import serializers
from .models import PatientProfile, MoodLog, HealthMetric, MedicalHistoryEntry
import logging

logger = logging.getLogger(__name__)


class PatientProfileSerializer(serializers.ModelSerializer):
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
            "treatment_plan",
            "pain_level",
            "last_appointment",
            "next_appointment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

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
            # Check file size
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError("Image file too large ( > 5MB )")

            # Check file type
            allowed_types = ["image/jpeg", "image/png", "image/gif"]
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    f"Invalid file type. Must be one of: {', '.join(allowed_types)}"
                )

            # Check dimensions (optional)
            try:
                from PIL import Image

                img = Image.open(value)
                max_dimensions = (2000, 2000)
                if img.width > max_dimensions[0] or img.height > max_dimensions[1]:
                    raise serializers.ValidationError(
                        f"Image dimensions too large. Max dimensions: {max_dimensions[0]}x{max_dimensions[1]}"
                    )
            except ImportError:
                logger.warning("PIL not installed, skipping dimension validation")
            except Exception as e:
                logger.error(f"Error validating image dimensions: {str(e)}")

        return value


class MoodLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodLog
        fields = ["id", "user", "mood", "timestamp"]


class HealthMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMetric
        fields = "__all__"
        read_only_fields = ["patient", "timestamp"]


class MedicalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalHistoryEntry
        fields = "__all__"
        read_only_fields = ["patient"]

# patient/serializers/patient_profile.py
from rest_framework import serializers
from patient.models.patient_profile import PatientProfile
import logging

logger = logging.getLogger(__name__)


class PatientProfileSerializer(serializers.ModelSerializer):
    blood_type = serializers.CharField(max_length=3, required=False, allow_null=True)
    pain_level = serializers.IntegerField(
        min_value=0, max_value=10, required=False, allow_null=True
    )
    user_name = serializers.SerializerMethodField()
    # Allow updating these name fields by removing read_only and adding required=False
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "unique_id",  # Add this field
            "user",
            "user_name",
            "first_name",  # New writable field
            "last_name",   # New writable field
            "email",
            "phone_number",
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
        read_only_fields = [
            "id",
            "unique_id",  # Add this field
            "user",
            "created_at",
            "updated_at"
        ]

    def get_user_name(self, obj):
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name if full_name else obj.user.username

    def validate_blood_type(self, value):
        valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        if value and value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid blood type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate_profile_pic(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError("Image file too large ( > 5MB )")

            allowed_types = ["image/jpeg", "image/png", "image/gif"]
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    f"Invalid file type. Must be one of: {', '.join(allowed_types)}"
                )

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

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        return super().update(instance, validated_data)

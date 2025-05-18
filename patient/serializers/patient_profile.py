# patient/serializers/patient_profile.py
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response
from patient.models.patient_profile import PatientProfile
from therapist.models import TherapistProfile
from therapist.serializers.therapist_profile import TherapistProfileSerializer
import logging

logger = logging.getLogger(__name__)


class PatientProfileSerializer(serializers.ModelSerializer):
    blood_type = serializers.CharField(max_length=3, required=False, allow_null=True)
    user_name = serializers.SerializerMethodField()
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", required=False)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "user",
            "user_name",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_pic",
            "blood_type",
            "gender",
            "emergency_contact",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
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
        logger.debug(
            f"PatientProfile update called with validated_data: {validated_data}"
        )
        user_data = validated_data.pop("user", {})
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        updated_instance = super().update(instance, validated_data)
        logger.debug(
            f"PatientProfile update completed. Updated instance: {updated_instance}"
        )
        return updated_instance


class TherapistProfileSerializer(serializers.ModelSerializer):
    # nested user fields
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    phone_number = serializers.CharField(source="user.phone_number", required=False)

    # explicit JSON/List fields
    available_days = serializers.JSONField(required=False)
    treatment_approaches = serializers.JSONField(required=False)
    languages_spoken = serializers.ListField(
        child=serializers.CharField(), required=False
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "phone_number",
            "specialization",
            "license_number",
            "years_of_experience",
            "bio",
            "available_days",
            "treatment_approaches",
            "license_expiry",
            "video_session_link",
            "languages_spoken",
            "profile_completion_percentage",
            "is_profile_complete",
            "verification_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if user_data:
            user = instance.user
            for attr, val in user_data.items():
                setattr(user, attr, val)
            user.save()
        updated = super().update(instance, validated_data)
        logger.debug(f"Updated TherapistProfile(id={instance.id}): {validated_data}")
        return updated


class TherapistProfileViewSet(viewsets.ModelViewSet):
    queryset = TherapistProfile.objects.all()
    serializer_class = TherapistProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as exc:
            # return the real field errors
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        self.perform_update(serializer)
        return Response(serializer.data)

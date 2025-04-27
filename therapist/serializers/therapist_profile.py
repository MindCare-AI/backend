# therapist/serializers/therapist_profile.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)
    username = serializers.SerializerMethodField()
    # Make these fields writable by removing read_only and adding required=False
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", required=False)
    treatment_approaches = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, default=list
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "specialization",
            "license_number",
            "years_of_experience",
            "bio",
            "profile_pic",
            "treatment_approaches",
            "available_days",
            "license_expiry",
            "video_session_link",
            "languages_spoken",
            "profile_completion_percentage",
            "is_profile_complete",
            "created_at",
            "updated_at",
            "verification_status",
        ]
        read_only_fields = [
            "id",
            "user",
            "username",
            "email",
            "created_at",
            "updated_at",
            "profile_completion_percentage",
            "is_profile_complete",
        ]

    def update(self, instance, validated_data):
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(
            f"TherapistProfile update called with validated_data: {validated_data}"
        )

        # Handle treatment_approaches separately to ensure it's always a list
        treatment_approaches = validated_data.get("treatment_approaches", [])
        if treatment_approaches is None:
            treatment_approaches = []
        validated_data["treatment_approaches"] = treatment_approaches

        user_data = validated_data.pop("user", {})
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        updated_instance = super().update(instance, validated_data)
        logger.debug(
            f"TherapistProfile update completed. Updated instance: {updated_instance}"
        )
        return updated_instance

    def get_username(self, obj):
        return obj.user.username

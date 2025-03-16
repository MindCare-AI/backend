# therapist/serializers/therapist_profile.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
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
            "created_at",
            "updated_at",
            "profile_completion_percentage",
            "is_profile_complete",
        ]

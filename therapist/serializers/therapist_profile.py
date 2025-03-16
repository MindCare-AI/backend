# therapist/serializers/therapist_profile.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)
    username = serializers.SerializerMethodField()  # Add this line

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "user",
            "username",  # Add this line
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
            "username",  # Add this line
            "created_at",
            "updated_at",
            "profile_completion_percentage",
            "is_profile_complete",
        ]

    def get_username(self, obj):  # Add this method
        return obj.user.username  # Access the username through the User model

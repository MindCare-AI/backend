# therapist/serializers/therapist_profile.py
from rest_framework import serializers
from therapist.models.therapist_profile import TherapistProfile


class TherapistProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)
    username = serializers.SerializerMethodField()
    # Make these fields writable by removing read_only and adding required=False
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)

    class Meta:
        model = TherapistProfile
        fields = [
            "id",
            "unique_id",  # Add this field
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
            "unique_id",  # Add this field
            "user",
            "username",
            "email",
            "phone_number",
            "created_at",
            "updated_at",
            "profile_completion_percentage",
            "is_profile_complete",
        ]

    def update(self, instance, validated_data):
        # Handle nested user data (first_name, last_name)
        user_data = validated_data.pop('user', {})
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        return super().update(instance, validated_data)

    def get_username(self, obj):
        return obj.user.username

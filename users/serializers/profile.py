# users/serializers/profile.py

from urllib.parse import urlparse
from django.conf import settings

# Import the app-specific serializers
from patient.serializers.patient_profile import (
    PatientProfileSerializer as AppPatientProfileSerializer,
)
from therapist.serializers.therapist_profile import (
    TherapistProfileSerializer as AppTherapistProfileSerializer,
)


# Proxy serializer that extends the app-specific serializer and adds app-specific functionality for the users app if needed.
class PatientProfileSerializer(AppPatientProfileSerializer):
    def update(self, instance, validated_data):
        profile_pic = validated_data.get("profile_pic")
        if isinstance(profile_pic, str):
            # Strip MEDIA_URL prefix from the URL and assign the relative path
            path = urlparse(profile_pic).path
            media_url = settings.MEDIA_URL
            if path.startswith(media_url):
                path = path[len(media_url) :]
            instance.profile_pic = path
            validated_data.pop("profile_pic")
        return super().update(instance, validated_data)


# Proxy serializer that extends the app-specific serializer and adds app-specific functionality for the users app if needed.
class TherapistProfileSerializer(AppTherapistProfileSerializer):
    def update(self, instance, validated_data):
        profile_pic = validated_data.get("profile_pic")
        if isinstance(profile_pic, str):
            # Strip MEDIA_URL prefix from the URL and assign the relative path
            path = urlparse(profile_pic).path
            media_url = settings.MEDIA_URL
            if path.startswith(media_url):
                path = path[len(media_url) :]
            instance.profile_pic = path
            validated_data.pop("profile_pic")
        return super().update(instance, validated_data)

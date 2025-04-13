# users/serializers/profile.py
from rest_framework import serializers
from users.validators.user_validators import (
    validate_profile_pic,
    validate_emergency_contact,
    validate_blood_type,
)

# Import the app-specific serializers
from patient.serializers.patient_profile import PatientProfileSerializer as AppPatientProfileSerializer
from therapist.serializers.therapist_profile import TherapistProfileSerializer as AppTherapistProfileSerializer


# Proxy serializer that extends the app-specific serializer and adds/overrides fields if needed
class PatientProfileSerializer(AppPatientProfileSerializer):
    """
    This serializer extends the core PatientProfileSerializer from the patient app
    and can add app-specific functionality for the users app if needed.
    """
    pass


# Proxy serializer that extends the app-specific serializer and adds/overrides fields if needed
class TherapistProfileSerializer(AppTherapistProfileSerializer):
    """
    This serializer extends the core TherapistProfileSerializer from the therapist app
    and can add app-specific functionality for the users app if needed.
    """
    pass

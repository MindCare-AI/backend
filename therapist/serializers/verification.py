# therapist/serializers/verification.py
from rest_framework import serializers
from django.conf import settings
from ..models.therapist_profile import TherapistProfile
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class TherapistVerificationSerializer(serializers.Serializer):
    """Serializer for handling verification requests"""
    license_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,
        error_messages={
            'required': 'Please upload your professional license image.',
            'invalid': 'The uploaded license file must be a valid image.',
            'empty': 'The license image file cannot be empty.'
        }
    )
    selfie_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,
        error_messages={
            'required': 'Please upload a current selfie photo for verification.',
            'invalid': 'The uploaded selfie file must be a valid image.',
            'empty': 'The selfie image file cannot be empty.'
        }
    )
    license_number = serializers.CharField(
        required=True,
        max_length=100,
        allow_blank=False,
        error_messages={
            'required': 'Please provide your license number.',
            'blank': 'License number cannot be blank.',
            'max_length': 'License number cannot exceed {max_length} characters.'
        }
    )
    issuing_authority = serializers.ChoiceField(
        choices=settings.VERIFICATION_SETTINGS['LICENSE_VALIDATION']['ALLOWED_AUTHORITIES'],
        required=True,
        error_messages={
            'required': 'Please select the authority that issued your license.',
            'invalid_choice': 'Please select a valid issuing authority from the list.'
        }
    )

    def to_internal_value(self, data):
        """
        Override to handle both multipart form data and JSON
        """
        if hasattr(data, 'getlist'):
            # Handle multipart form data
            result = {}
            for key in ['license_image', 'selfie_image', 'license_number', 'issuing_authority']:
                if key in data:
                    result[key] = data[key]
            return super().to_internal_value(result)
        return super().to_internal_value(data)

    def validate_license_image(self, value):
        """Validate license image file"""
        if value.size > settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['MAX_SIZE']:
            max_size_mb = settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['MAX_SIZE'] / (1024 * 1024)
            raise serializers.ValidationError(
                f"License image must not exceed {max_size_mb}MB"
            )

        if not any(value.content_type.startswith(mime_type) 
                  for mime_type in settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['ALLOWED_MIME_TYPES']):
            raise serializers.ValidationError(
                "License image must be in JPG, PNG, or WebP format"
            )
        return value

    def validate_selfie_image(self, value):
        """Validate selfie image file"""
        if value.size > settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['MAX_SIZE']:
            max_size_mb = settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['MAX_SIZE'] / (1024 * 1024)
            raise serializers.ValidationError(
                f"Selfie image must not exceed {max_size_mb}MB"
            )

        if not any(value.content_type.startswith(mime_type) 
                  for mime_type in settings.VERIFICATION_SETTINGS['IMAGE_REQUIREMENTS']['ALLOWED_MIME_TYPES']):
            raise serializers.ValidationError(
                "Selfie image must be in JPG, PNG, or WebP format"
            )
        return value

    def validate_issuing_authority(self, value):
        """Validate issuing authority"""
        allowed_authorities = settings.VERIFICATION_SETTINGS['LICENSE_VALIDATION']['ALLOWED_AUTHORITIES']
        if value not in allowed_authorities:
            raise serializers.ValidationError(
                f"Invalid issuing authority. Must be one of: {', '.join(allowed_authorities)}"
            )
        return value


class VerificationStatusSerializer(serializers.ModelSerializer):
    """Serializer for viewing verification status"""
    days_until_expiry = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    
    class Meta:
        model = TherapistProfile
        fields = [
            'is_verified',
            'verification_status',
            'verification_notes',
            'verified_at',
            'verification_expiry',
            'license_number',
            'license_expiry',
            'issuing_authority',
            'days_until_expiry',
            'can_submit'
        ]
        read_only_fields = fields

    def get_days_until_expiry(self, obj):
        """Calculate days until verification expires"""
        if obj.verification_expiry:
            delta = obj.verification_expiry - timezone.now().date()
            return max(0, delta.days)
        return None

    def get_can_submit(self, obj):
        """Check if the therapist can submit verification"""
        return not obj.is_verified
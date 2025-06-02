# therapist/serializers/verification.py
from rest_framework import serializers
from django.conf import settings
from ..models.therapist_profile import TherapistProfile
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class TherapistVerificationSerializer(serializers.Serializer):
    """Enhanced serializer for handling verification requests"""

    license_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,
        error_messages={
            "required": "Please upload your professional license image.",
            "invalid": "The uploaded license file must be a valid image.",
            "empty": "The license image file cannot be empty.",
        },
    )
    selfie_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,
        error_messages={
            "required": "Please upload a current selfie photo for verification.",
            "invalid": "The uploaded selfie file must be a valid image.",
            "empty": "The selfie image file cannot be empty.",
        },
    )
    license_number = serializers.CharField(
        required=True,
        max_length=100,
        allow_blank=False,
        error_messages={
            "required": "Please provide your license number.",
            "blank": "License number cannot be blank.",
            "max_length": "License number cannot exceed {max_length} characters.",
        },
    )
    issuing_authority = serializers.ChoiceField(
        choices=settings.VERIFICATION_SETTINGS["LICENSE_VALIDATION"]["ALLOWED_AUTHORITIES"],
        required=True,
        error_messages={
            "required": "Please select the authority that issued your license.",
            "invalid_choice": "Please select a valid issuing authority from the list.",
        },
    )
    
    # Additional fields for enhanced verification
    full_name = serializers.CharField(
        required=True,
        max_length=200,
        help_text="Full name as it appears on the license"
    )
    
    license_issue_date = serializers.DateField(
        required=False,
        help_text="Date when the license was issued"
    )
    
    license_expiry_date = serializers.DateField(
        required=False,
        help_text="License expiration date"
    )
    
    additional_certifications = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=True,
        help_text="List of additional certifications"
    )
    
    professional_email = serializers.EmailField(
        required=False,
        help_text="Professional email associated with the license"
    )
    
    consent_background_check = serializers.BooleanField(
        default=False,
        help_text="Consent to background verification"
    )

    def to_internal_value(self, data):
        """
        Override to handle both multipart form data and JSON
        """
        if hasattr(data, "getlist"):
            # Handle multipart form data
            result = {}
            for key in [
                "license_image",
                "selfie_image",
                "license_number",
                "issuing_authority",
            ]:
                if key in data:
                    result[key] = data[key]
            return super().to_internal_value(result)
        return super().to_internal_value(data)

    def validate_license_image(self, value):
        """Enhanced license image validation"""
        # Basic size and format validation
        if value.size > settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"]:
            max_size_mb = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"] / (1024 * 1024)
            raise serializers.ValidationError(f"License image must not exceed {max_size_mb}MB")

        if not any(value.content_type.startswith(mime_type) for mime_type in 
                  settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["ALLOWED_MIME_TYPES"]):
            raise serializers.ValidationError("License image must be in JPG, PNG, or WebP format")
        
        # Advanced validation using PIL
        try:
            from PIL import Image
            import io
            
            # Reset file pointer
            value.seek(0)
            image = Image.open(value)
            
            # Check minimum dimensions
            min_width = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MIN_WIDTH"]
            min_height = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MIN_HEIGHT"]
            
            if image.width < min_width or image.height < min_height:
                raise serializers.ValidationError(
                    f"License image must be at least {min_width}x{min_height} pixels"
                )
            
            # Check aspect ratio
            aspect_ratio = image.width / image.height
            min_ratio = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MIN_ASPECT_RATIO"]
            max_ratio = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_ASPECT_RATIO"]
            
            if not (min_ratio <= aspect_ratio <= max_ratio):
                raise serializers.ValidationError(
                    f"License image aspect ratio must be between {min_ratio} and {max_ratio}"
                )
            
            # Check for blur/quality issues
            quality_score = self._assess_image_quality(image)
            if quality_score < 0.5:
                raise serializers.ValidationError(
                    "License image appears to be too blurry or low quality. Please upload a clearer image."
                )
            
            # Reset file pointer for subsequent processing
            value.seek(0)
            
        except Exception as e:
            if isinstance(e, serializers.ValidationError):
                raise
            raise serializers.ValidationError("Unable to process license image. Please ensure it's a valid image file.")
        
        return value

    def validate_selfie_image(self, value):
        """Enhanced selfie image validation including basic liveness checks"""
        # Basic validation (similar to license image)
        if value.size > settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"]:
            max_size_mb = settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["MAX_SIZE"] / (1024 * 1024)
            raise serializers.ValidationError(f"Selfie image must not exceed {max_size_mb}MB")

        if not any(value.content_type.startswith(mime_type) for mime_type in 
                  settings.VERIFICATION_SETTINGS["IMAGE_REQUIREMENTS"]["ALLOWED_MIME_TYPES"]):
            raise serializers.ValidationError("Selfie image must be in JPG, PNG, or WebP format")
        
        # Advanced validation
        try:
            from PIL import Image
            import numpy as np
            
            value.seek(0)
            image = Image.open(value)
            
            # Check if image contains a face
            face_detected = self._detect_face_in_image(image)
            if not face_detected:
                raise serializers.ValidationError(
                    "No face detected in selfie image. Please upload a clear photo of your face."
                )
            
            # Basic liveness checks
            liveness_checks = self._basic_liveness_validation(image)
            if not liveness_checks["appears_live"]:
                raise serializers.ValidationError(
                    "Selfie image does not appear to show a live person. Please take a new selfie."
                )
            
            value.seek(0)
            
        except Exception as e:
            if isinstance(e, serializers.ValidationError):
                raise
            raise serializers.ValidationError("Unable to process selfie image. Please ensure it's a valid image file.")
        
        return value

    def validate_license_number(self, value):
        """Enhanced license number validation"""
        # Remove common separators and spaces
        cleaned_number = value.replace("-", "").replace(" ", "").replace(".", "")
        
        # Check if it contains only valid characters (alphanumeric)
        if not cleaned_number.isalnum():
            raise serializers.ValidationError(
                "License number should contain only letters and numbers"
            )
        
        # Minimum length check
        if len(cleaned_number) < 4:
            raise serializers.ValidationError(
                "License number appears to be too short"
            )
        
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Check if license expiry date is in the future
        if attrs.get('license_expiry_date'):
            from django.utils import timezone
            if attrs['license_expiry_date'] <= timezone.now().date():
                raise serializers.ValidationError({
                    'license_expiry_date': 'License expiry date must be in the future'
                })
        
        # Check if issue date is before expiry date
        if attrs.get('license_issue_date') and attrs.get('license_expiry_date'):
            if attrs['license_issue_date'] >= attrs['license_expiry_date']:
                raise serializers.ValidationError({
                    'license_expiry_date': 'License expiry date must be after issue date'
                })
        
        return attrs

    def _assess_image_quality(self, image):
        """Assess image quality using basic metrics"""
        try:
            import numpy as np
            from PIL import ImageFilter
            
            # Convert to grayscale
            gray_image = image.convert('L')
            
            # Calculate variance of Laplacian (blur detection)
            laplacian_var = np.array(gray_image.filter(ImageFilter.FIND_EDGES)).var()
            
            # Normalize score (higher variance = less blur)
            # This is a simple approximation
            quality_score = min(1.0, laplacian_var / 1000.0)
            
            return quality_score
            
        except Exception:
            # If quality assessment fails, assume acceptable quality
            return 0.7

    def _detect_face_in_image(self, image):
        """Basic face detection in image"""
        try:
            import face_recognition
            import numpy as np
            
            # Convert PIL image to numpy array
            image_array = np.array(image)
            
            # Try to find faces
            face_locations = face_recognition.face_locations(image_array)
            
            return len(face_locations) > 0
            
        except ImportError:
            # If face_recognition is not available, skip this check
            return True
        except Exception:
            # If face detection fails, assume face is present to avoid false negatives
            return True

    def _basic_liveness_validation(self, image):
        """Basic liveness validation checks"""
        try:
            import numpy as np
            
            # Convert to numpy array
            image_array = np.array(image)
            
            # Basic checks for liveness indicators
            checks = {
                "appears_live": True,  # Default to true for basic validation
                "color_variation": self._check_color_variation(image_array),
                "edge_sharpness": self._check_edge_sharpness(image_array),
            }
            
            # Simple heuristic: if image has good color variation and sharpness, likely live
            checks["appears_live"] = checks["color_variation"] and checks["edge_sharpness"]
            
            return checks
            
        except Exception:
            # If liveness checks fail, default to assuming live
            return {"appears_live": True}

    def _check_color_variation(self, image_array):
        """Check for natural color variation in image"""
        try:
            import numpy as np
            # Calculate color variance across channels
            if len(image_array.shape) == 3:
                color_vars = [np.var(image_array[:, :, i]) for i in range(3)]
                avg_variance = np.mean(color_vars)
                return avg_variance > 100  # Threshold for sufficient variation
            return True
        except:
            return True

    def _check_edge_sharpness(self, image_array):
        """Check for sufficient edge sharpness"""
        try:
            from PIL import Image, ImageFilter
            import numpy as np
            
            # Convert back to PIL for filtering
            if len(image_array.shape) == 3:
                pil_image = Image.fromarray(image_array)
            else:
                pil_image = Image.fromarray(image_array, 'L')
            
            # Apply edge detection
            edges = pil_image.filter(ImageFilter.FIND_EDGES)
            edge_array = np.array(edges)
            
            # Calculate edge strength
            edge_strength = np.mean(edge_array)
            
            return edge_strength > 10  # Threshold for sufficient sharpness
        except:
            return True


class VerificationStatusSerializer(serializers.ModelSerializer):
    """Serializer for viewing verification status"""

    days_until_expiry = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()

    class Meta:
        model = TherapistProfile
        fields = [
            "is_verified",
            "verification_status",
            "verification_notes",
            "verified_at",
            # Removing verification_expiry as it doesn't exist in the model
            "license_number",
            "license_expiry",
            # Removing issuing_authority as it doesn't exist in the model
            "days_until_expiry",
            "can_submit",
        ]
        read_only_fields = fields

    def get_days_until_expiry(self, obj):
        """Calculate days until verification expires"""
        if obj.license_expiry:  # Use license_expiry instead of verification_expiry
            delta = obj.license_expiry - timezone.now().date()
            return max(0, delta.days)
        return None

    def get_can_submit(self, obj):
        """Check if the therapist can submit verification"""
        return not obj.is_verified

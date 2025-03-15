from rest_framework.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


def validate_emergency_contact(value):
    """
    Validate emergency contact information
    Required fields: name, relationship, phone
    """
    required_fields = ["name", "relationship", "phone"]
    if not value:
        return value

    if not all(field in value for field in required_fields):
        raise ValidationError(
            f"Emergency contact must include: {', '.join(required_fields)}"
        )

    if not value["phone"].replace("+", "").isdigit():
        raise ValidationError("Phone number must contain only digits and optional +")

    logger.debug(f"Emergency contact validated: {value}")
    return value


def validate_blood_type(value):
    """
    Validate blood type
    Valid types: A+, A-, B+, B-, AB+, AB-, O+, O-
    """
    if not value:
        return value

    valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    if value not in valid_types:
        raise ValidationError(
            f"Invalid blood type. Must be one of: {', '.join(valid_types)}"
        )

    return value


def validate_profile_pic(value):
    """
    Validate profile picture
    - Size limit: 5MB
    - Must be an image file
    """
    if not value:
        return value

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Image file too large ( > 5MB )")

    if not value.content_type.startswith("image/"):
        raise ValidationError("File must be an image")

    return value

# users/validators/user_validators.py
from rest_framework.exceptions import ValidationError


def validate_emergency_contact(value):
    required_fields = ["name", "relationship", "phone"]
    if value and not all(field in value for field in required_fields):
        raise ValidationError(
            f"Emergency contact must include: {', '.join(required_fields)}"
        )
    if value and not value["phone"].replace("+", "").isdigit():
        raise ValidationError("Phone number must contain only digits and optional +")
    return value


def validate_blood_type(value):
    valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    if value and value not in valid_types:
        raise ValidationError(
            f"Invalid blood type. Must be one of: {', '.join(valid_types)}"
        )
    return value


def validate_profile_pic(value):
    if value and value.size > 5 * 1024 * 1024:
        raise ValidationError("Image file too large ( > 5MB )")
    if value and not value.content_type.startswith("image/"):
        raise ValidationError("File must be an image")
    return value

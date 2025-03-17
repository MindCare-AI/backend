# media_handler/utils.py
import os
from django.core.exceptions import ValidationError


def get_human_readable_size(size_in_bytes):
    """Convert bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f}{unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f}TB"


def validate_file_extension(filename, allowed_extensions):
    """Validate file extension against allowed list."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f"Invalid file extension '{ext}'. "
            f"Allowed extensions: {', '.join(allowed_extensions)}"
        )
    return True

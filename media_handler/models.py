# media_handler/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import os
import magic
import logging
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger(__name__)


class MediaFile(models.Model):
    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("document", "Document"),
    )

    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(editable=False)
    mime_type = models.CharField(max_length=100, editable=False)

    # Add user relationship
    uploaded_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="uploaded_media",
        null=True,
        blank=True,
    )

    # Generic relation fields, updated to use standard integer IDs.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="media_files",
    )
    object_id = models.PositiveIntegerField(
        null=True, blank=True, db_index=True, help_text="ID of the related object"
    )
    content_object = GenericForeignKey("content_type", "object_id")

    def clean(self):
        """Validate file size and media type before saving."""
        if self.file and self.file.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"File size cannot exceed {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB"
            )

        if self.media_type and self.mime_type:
            allowed_mime_types = settings.ALLOWED_MEDIA_TYPES.get(self.media_type, [])
            if self.mime_type not in allowed_mime_types:
                raise ValidationError(
                    f"Invalid MIME type {self.mime_type} for {self.media_type}. "
                    f"Allowed types: {', '.join(allowed_mime_types)}"
                )

    def save(self, *args, **kwargs):
        """Save the file and validate its properties."""
        if self.file:
            self.file_size = self.file.size
            self.mime_type = self._get_mime_type()
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    def _get_mime_type(self):
        """Determine MIME type of uploaded file with enhanced error handling."""
        if not self.file:
            return None

        try:
            self.file.seek(0)
            mime = magic.from_buffer(self.file.read(2048), mime=True)
            self.file.seek(0)
            return mime
        except magic.MagicException as e:
            logger.error(f"Magic library error: {str(e)}")
            return "application/octet-stream"
        except Exception as e:
            logger.error(f"Unexpected error determining MIME type: {str(e)}")
            return "application/octet-stream"

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def link_to_profile(self, profile):
        """Link media to a profile using standard ID"""
        self.content_type = ContentType.objects.get_for_model(profile.__class__)
        self.object_id = profile.id
        self.save()

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["-uploaded_at"]),
        ]

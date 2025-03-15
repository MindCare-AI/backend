# media_handler/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import os
import magic
import logging
from django.core.exceptions import ValidationError

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

    # Optional generic relation fields
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            self.mime_type = self._get_mime_type()
        self.full_clean()  # Add validation before saving
        super().save(*args, **kwargs)

    def _get_mime_type(self):
        """
        Determine MIME type of uploaded file with enhanced error handling
        and validation against allowed types.
        """
        if not self.file:
            return None

        # Mapping of media types to allowed MIME types
        ALLOWED_MIME_TYPES = {
            "image": ["image/jpeg", "image/png", "image/gif"],
            "video": ["video/mp4", "video/quicktime", "video/x-msvideo"],
            "audio": ["audio/mpeg", "audio/wav", "audio/ogg"],
            "document": [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
            ],
        }

        try:
            # Read file magic number
            self.file.seek(0)
            mime = magic.from_buffer(self.file.read(2048), mime=True)
            self.file.seek(0)

            # Validate against allowed types
            if self.media_type and self.media_type in ALLOWED_MIME_TYPES:
                if mime not in ALLOWED_MIME_TYPES[self.media_type]:
                    raise ValidationError(
                        f"Invalid MIME type {mime} for {self.media_type}. "
                        f"Allowed types: {', '.join(ALLOWED_MIME_TYPES[self.media_type])}"
                    )

            return mime

        except magic.MagicException as e:
            logger.error(f"Magic library error: {str(e)}")
            return "application/octet-stream"
        except ValidationError as e:
            logger.error(f"MIME type validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error determining MIME type: {str(e)}")
            return "application/octet-stream"
        finally:
            # Ensure file pointer is reset
            if self.file:
                self.file.seek(0)

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    class Meta:
        ordering = ["-uploaded_at"]

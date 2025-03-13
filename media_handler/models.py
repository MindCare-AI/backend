#media_handler/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import os


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
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, 
                                    related_name='uploaded_media', null=True, blank=True)

    # Generic relation fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            self.mime_type = self._get_mime_type()
        super().save(*args, **kwargs)

    def _get_mime_type(self):
        import magic
        try:
            mime = magic.from_buffer(self.file.read(1024), mime=True)
            self.file.seek(0)  # Reset file pointer after reading
            return mime
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error determining MIME type: {str(e)}")
            return "application/octet-stream"  # Default mime type

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    class Meta:
        ordering = ["-uploaded_at"]

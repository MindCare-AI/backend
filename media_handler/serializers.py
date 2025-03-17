# media_handler/serializers.py
from rest_framework import serializers
from .models import MediaFile
import os
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class MediaFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    file = serializers.FileField()
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(), required=False, allow_null=True
    )
    object_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = MediaFile
        fields = [
            "id",
            "file",
            "url",
            "title",
            "description",
            "media_type",
            "file_size",
            "mime_type",
            "uploaded_at",
            "filename",
            "content_type",
            "object_id",
            "uploaded_by",
        ]
        read_only_fields = ["file_size", "mime_type", "uploaded_at"]

    def get_url(self, obj):
        """Generate absolute URL for file access."""
        request = self.context.get("request")
        if obj.file and hasattr(obj.file, "url"):
            return request.build_absolute_uri(obj.file.url)
        return None

    def validate_file(self, value):
        """Validate file size and type."""
        max_size = settings.MAX_UPLOAD_SIZE
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size cannot exceed {max_size / (1024 * 1024)}MB"
            )

        ext = os.path.splitext(value.name)[1].lower()
        media_type = self.initial_data.get("media_type")
        allowed_extensions = settings.ALLOWED_MEDIA_TYPES.get(media_type, [])

        if media_type and ext not in allowed_extensions:
            raise serializers.ValidationError(
                {
                    "file": f"Invalid file extension for {media_type}. "
                    f"Allowed extensions: {', '.join(allowed_extensions)}"
                }
            )

        return value

    def validate(self, data):
        """Validate related object references."""
        content_type = data.get("content_type")
        object_id = data.get("object_id")

        if bool(content_type) != bool(object_id):
            raise serializers.ValidationError(
                {
                    "content_type": "Both content_type and object_id must be provided together",
                    "object_id": "Both content_type and object_id must be provided together",
                }
            )

        if content_type and object_id:
            model_class = content_type.model_class()
            if not any(
                isinstance(field, models.UUIDField)
                for field in model_class._meta.fields
            ):
                raise serializers.ValidationError(
                    {
                        "content_type": f"Model {model_class.__name__} does not have a UUID field"
                    }
                )

        return data

    def create(self, validated_data):
        """Create media file with current user."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["uploaded_by"] = request.user
        return super().create(validated_data)

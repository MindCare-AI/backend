#media_handler/serializers.py
from rest_framework import serializers
from .models import MediaFile


class MediaFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MediaFile
        fields = [
            "id",
            "url",
            "title",
            "description",
            "media_type",
            "file_size",
            "mime_type",
            "uploaded_at",
            "filename",
        ]
        read_only_fields = ["file_size", "mime_type", "uploaded_at"]

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and hasattr(obj.file, "url"):
            return request.build_absolute_uri(obj.file.url)
        return None

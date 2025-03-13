#media_handler/serializers.py
from rest_framework import serializers
from .models import MediaFile
import os


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

    def validate_file(self, value):
        # Check file size (limit to 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB")
            
        # Validate file extensions for security
        allowed_extensions = {
            'image': ['.jpg', '.jpeg', '.png', '.gif'],
            'video': ['.mp4', '.mov', '.avi'],
            'audio': ['.mp3', '.wav', '.ogg'],
            'document': ['.pdf', '.doc', '.docx', '.txt']
        }
        
        # Get file extension
        ext = os.path.splitext(value.name)[1].lower()
        
        # Check media type from request data
        media_type = self.initial_data.get('media_type')
        if media_type and media_type in allowed_extensions:
            if ext not in allowed_extensions[media_type]:
                raise serializers.ValidationError(
                    f"Invalid file extension for {media_type}. Allowed: {', '.join(allowed_extensions[media_type])}")
                
        return value

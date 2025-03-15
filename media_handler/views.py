# media_handler/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.conf import settings
import logging
from .models import MediaFile
from .serializers import MediaFileSerializer
from .permissions import IsUploaderOrReadOnly

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(description="List all media files", tags=["Media"]),
    retrieve=extend_schema(
        description="Retrieve a specific media file", tags=["Media"]
    ),
    create=extend_schema(description="Upload a new media file", tags=["Media"]),
    update=extend_schema(description="Update media file details", tags=["Media"]),
    destroy=extend_schema(description="Delete a media file", tags=["Media"]),
)
class MediaFileViewSet(viewsets.ModelViewSet):
    queryset = MediaFile.objects.all()
    serializer_class = MediaFileSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated, IsUploaderOrReadOnly]

    def perform_create(self, serializer):
        try:
            # Validate file size and type
            file_obj = self.request.FILES.get("file")
            if not file_obj:
                raise ValidationError("No file provided")

            if file_obj.size > settings.MAX_UPLOAD_SIZE:
                raise ValidationError(
                    f"File size exceeds {settings.MAX_UPLOAD_SIZE} bytes"
                )

            content_type = file_obj.content_type
            media_type = self.request.data.get("media_type", "")

            if media_type not in settings.ALLOWED_MEDIA_TYPES:
                raise ValidationError(f"Invalid media type: {media_type}")

            if content_type not in settings.ALLOWED_MEDIA_TYPES[media_type]:
                raise ValidationError(
                    f"Invalid content type for {media_type}: {content_type}"
                )

            # Save the file
            serializer.save(
                uploaded_by=self.request.user,
                file_size=file_obj.size,
                content_type=content_type,
            )

            logger.info(f"File uploaded successfully: {file_obj.name}")

        except ValidationError as e:
            logger.error(f"File upload validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {str(e)}")
            raise ValidationError("File upload failed")

    def get_queryset(self):
        queryset = MediaFile.objects.all()

        # Apply filters
        filters = {}

        # Media type filter
        media_type = self.request.query_params.get("media_type")
        if media_type:
            filters["media_type"] = media_type

        # Content type and object filters
        content_type_id = self.request.query_params.get("content_type_id")
        object_id = self.request.query_params.get("object_id")
        if content_type_id and object_id:
            filters.update({"content_type_id": content_type_id, "object_id": object_id})

        # User uploads filter
        if self.request.query_params.get("my_uploads"):
            filters["uploaded_by"] = self.request.user

        return queryset.filter(**filters)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Verify file integrity and scan for malware"""
        try:
            media_file = self.get_object()
            verification_result = media_file.verify_file()

            return Response(
                {
                    "verified": verification_result,
                    "message": "File verification completed",
                }
            )
        except Exception as e:
            logger.error(f"File verification error: {str(e)}")
            return Response(
                {"error": "File verification failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

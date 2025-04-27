# media_handler/views.py
from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
import logging
from .models import MediaFile
from .serializers import MediaFileSerializer
from .permissions import IsUploaderOrReadOnly

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all media files",
        tags=["Media"],
        parameters=[
            OpenApiParameter(
                name="media_type",
                type=OpenApiTypes.STR,
                description="Filter by media type (image, video, audio, document)",
            ),
            OpenApiParameter(
                name="content_type_id",
                type=OpenApiTypes.INT,
                description="Filter by content type ID",
            ),
            OpenApiParameter(
                name="object_id",
                type=OpenApiTypes.UUID,
                description="Filter by object UUID",
            ),
            OpenApiParameter(
                name="my_uploads",
                type=OpenApiTypes.BOOL,
                description="Filter to show only user's uploads",
            ),
        ],
    ),
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
        file_obj = self.request.FILES.get("file")
        if not file_obj:
            raise ValidationError({"file": "No file provided"})

        serializer.save(
            uploaded_by=self.request.user,
            file_size=file_obj.size,
            mime_type=file_obj.content_type
        )

    def get_queryset(self):
        queryset = MediaFile.objects.all()
        filters = {}

        media_type = self.request.query_params.get("media_type")
        if media_type:
            filters["media_type"] = media_type

        content_type_id = self.request.query_params.get("content_type_id")
        object_id = self.request.query_params.get("object_id")
        if content_type_id and object_id:
            filters.update({"content_type_id": content_type_id, "object_id": object_id})

        if self.request.query_params.get("my_uploads"):
            filters["uploaded_by"] = self.request.user

        return queryset.filter(**filters)

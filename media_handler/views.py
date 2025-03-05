from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import MediaFile
from .serializers import MediaFileSerializer


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
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

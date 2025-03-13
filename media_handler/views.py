#media_handler/views.py
from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import MediaFile
from .serializers import MediaFileSerializer
from .permissions import IsUploaderOrReadOnly


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
        serializer.save(uploaded_by=self.request.user)
    
    def get_queryset(self):
        queryset = MediaFile.objects.all()
        
        # Filter by media type
        media_type = self.request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
            
        # Filter by content type and object id
        content_type_id = self.request.query_params.get('content_type_id')
        object_id = self.request.query_params.get('object_id')
        if content_type_id and object_id:
            queryset = queryset.filter(content_type_id=content_type_id, object_id=object_id)
            
        # Filter by uploader
        if self.request.query_params.get('my_uploads'):
            queryset = queryset.filter(uploaded_by=self.request.user)
            
        return queryset

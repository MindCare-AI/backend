#messaging/mixins/edit_history.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from ..models import MessageEditHistory
import logging

logger = logging.getLogger(__name__)

class EditHistoryMixin:
    """Mixin to add ArrayField-based edit history functionality to message viewsets"""
    
    @extend_schema(
        summary="Get Edit History",
        description="Retrieves the edit history of a message including current content and an array of previous edit entries.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "current": {"type": "string"},
                    "history": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def edit_history(self, request, pk=None):
        """Get the edit history of a message using its ArrayField"""
        try:
            message = self.get_object()
            return Response({
                "current": message.content,
                "history": message.edit_history  # Assuming this is an ArrayField containing edit history objects
            })
        except Exception as e:
            logger.error(f"Error fetching edit history: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to fetch edit history"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_update(self, serializer):
        instance = serializer.instance
        new_content = serializer.validated_data.get('content', instance.content)

        if instance.content != new_content:
            # Initialize edit_history if needed
            if instance.edit_history is None:
                instance.edit_history = []

            # Add detailed edit record
            edit_entry = {
                'previous_content': instance.content,
                'edited_at': timezone.now().isoformat(),
                'edited_by': {
                    'id': str(self.request.user.id),
                    'username': self.request.user.username
                }
            }
            
            instance.edit_history.append(edit_entry)
            instance.edited = True
            instance.edited_at = timezone.now()
            instance.edited_by = self.request.user

        serializer.save()
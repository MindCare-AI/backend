from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class EditHistoryMixin:
    """Mixin to add edit history functionality to message viewsets"""
    
    @action(detail=True, methods=['get'])
    def edit_history(self, request, pk=None):
        """Get the edit history of a message"""
        try:
            message = self.get_object()
            return Response({
                "current": message.content,
                "history": message.edit_history or [],
                "edited_at": message.edited_at,
                "edited_by": {
                    "id": message.edited_by.id,
                    "name": message.edited_by.get_full_name()
                } if message.edited_by else None
            })
        except Exception as e:
            logger.error(f"Error fetching edit history: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to fetch edit history"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_update(self, serializer):
        """Override perform_update to track edit history"""
        instance = serializer.instance
        
        # Store current version in edit history
        if instance.content != serializer.validated_data.get('content'):
            history_entry = {
                "content": instance.content,
                "edited_at": instance.edited_at.isoformat() if instance.edited_at else None,
                "edited_by": {
                    "id": instance.edited_by.id,
                    "name": instance.edited_by.get_full_name()
                } if instance.edited_by else None
            }
            
            # Initialize edit_history if None
            if not instance.edit_history:
                instance.edit_history = []
            
            instance.edit_history.append(history_entry)
            
            # Update edit metadata
            instance.edited = True
            instance.edited_at = timezone.now()
            instance.edited_by = self.request.user
            
        serializer.save()
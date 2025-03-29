# messaging/mixins/edit_history.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from django.contrib.contenttypes.models import ContentType
import logging

logger = logging.getLogger(__name__)


class EditHistoryMixin:
    """Mixin to add edit history functionality to message viewsets"""

    @extend_schema(
        description="Get edit history for a message",
        summary="Get Edit History",
        tags=["Message"],
    )
    @action(detail=True, methods=["get"])
    def edit_history(self, request, pk=None):
        """Get the edit history for a message"""
        try:
            instance = self.get_object()

            # Check if user can view history (participant or message owner)
            if not (
                instance.sender == request.user
                or request.user.is_staff
                or instance.conversation.participants.filter(
                    id=request.user.id
                ).exists()
            ):
                return Response(
                    {"error": "You don't have permission to view edit history"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # For models using Array field for history
            if hasattr(instance, "edit_history") and isinstance(
                instance.edit_history, list
            ):
                history = instance.edit_history
            # For models using ContentType and GenericForeignKey
            else:
                from ..models.base import MessageEditHistory

                history_records = MessageEditHistory.objects.filter(
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                ).order_by("-edited_at")

                history = [
                    {
                        "previous_content": record.previous_content,
                        "edited_at": record.edited_at.isoformat(),
                        "edited_by": {
                            "id": record.edited_by.id if record.edited_by else None,
                            "username": record.edited_by.username
                            if record.edited_by
                            else "Unknown",
                        },
                    }
                    for record in history_records
                ]

            return Response(
                {
                    "current": {
                        "content": instance.content,
                        "edited_at": instance.edited_at.isoformat()
                        if instance.edited_at
                        else None,
                        "edited_by": instance.edited_by.id
                        if instance.edited_by
                        else None,
                    },
                    "history": history,
                }
            )

        except Exception as e:
            logger.error(f"Error getting edit history: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to retrieve edit history: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_update(self, serializer):
        """Handle updating a message with proper edit history tracking"""
        instance = serializer.instance
        new_content = serializer.validated_data.get("content", instance.content)

        if instance.content != new_content:
            # For models using Array field for history
            if hasattr(instance, "edit_history") and hasattr(instance, "edit_history"):
                # Initialize edit_history if needed
                if instance.edit_history is None:
                    instance.edit_history = []

                # Add detailed edit record
                edit_entry = {
                    "previous_content": instance.content,
                    "edited_at": timezone.now().isoformat(),
                    "edited_by": {
                        "id": str(self.request.user.id),
                        "username": self.request.user.username,
                    },
                }

                instance.edit_history.append(edit_entry)
            # For models using ContentType and GenericForeignKey
            else:
                try:
                    from ..models.base import MessageEditHistory

                    MessageEditHistory.objects.create(
                        content_type=ContentType.objects.get_for_model(instance),
                        object_id=instance.id,
                        previous_content=instance.content,
                        edited_by=self.request.user,
                    )
                except Exception as e:
                    logger.error(
                        f"Error creating edit history: {str(e)}", exc_info=True
                    )

            # Update edit metadata
            instance.edited = True
            instance.edited_at = timezone.now()
            instance.edited_by = self.request.user

        # Save the updated instance
        serializer.save()

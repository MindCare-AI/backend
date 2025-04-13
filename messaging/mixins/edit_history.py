# messaging/mixins/edit_history.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
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
        """Retrieve the edit history of a specific message."""
        try:
            message = self.get_object()
            if not hasattr(message, "edit_history"):
                return Response(
                    {"error": "This message does not have an edit history."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Assuming `edit_history` is a field or method on the message model
            history = message.edit_history
            return Response(history, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

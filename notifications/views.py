# notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from .models import Notification
from .serializers import NotificationSerializer, NotificationUpdateSerializer
import logging

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        """Get notifications for the current user with type information."""
        return (
            Notification.objects.filter(user=self.request.user)
            .select_related("notification_type")
            .order_by("-created_at")
        )

    @extend_schema(
        description="Update notification status",
        request=NotificationUpdateSerializer,
        responses={200: NotificationSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                instance = self.get_object()
                serializer = NotificationUpdateSerializer(
                    instance, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(NotificationSerializer(instance).data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating notification: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Mark all unread notifications as read",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                },
            }
        },
    )
    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        try:
            with transaction.atomic():
                updated = request.user.notifications.filter(read=False).update(
                    read=True
                )
                return Response({"status": "success", "count": updated})
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

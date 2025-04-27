# notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.core.cache import cache
from .models import Notification, NotificationType
from .serializers import NotificationSerializer, NotificationTypeSerializer, NotificationUpdateSerializer
import logging

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        """Get notifications for the current user with type information and caching."""
        cache_key = f'user_notifications_{self.request.user.id}'
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = (
                Notification.objects.filter(user=self.request.user)
                .select_related("notification_type")
                .order_by("-created_at")
            )
            cache.set(cache_key, queryset, timeout=300)  # Cache for 5 minutes
            
        return queryset

    @extend_schema(
        description="Update notification status",
        request=NotificationUpdateSerializer,
        responses={200: NotificationSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        """Update notification with cache invalidation"""
        try:
            with transaction.atomic():
                response = super().partial_update(request, *args, **kwargs)
                if response.status_code == 200:
                    # Invalidate caches
                    cache.delete(f'user_notifications_{request.user.id}')
                    cache.delete(f'notification_count_{request.user.id}')
                return response
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating notification: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Get notification count for the current user",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                },
            }
        },
    )
    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        """Get notification count with caching"""
        try:
            cache_key = f'notification_count_{request.user.id}'
            count = cache.get(cache_key)
            
            if count is None:
                count = Notification.objects.filter(user=request.user).count()
                cache.set(cache_key, count, timeout=60)  # Cache for 1 minute
                
            return Response({"count": count})
        except Exception as e:
            logger.error(f"Error fetching notification count: {str(e)}")
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
        """Mark all notifications as read with cache invalidation"""
        try:
            with transaction.atomic():
                updated = request.user.notifications.filter(read=False).update(read=True)
                # Invalidate user's notification cache
                cache.delete(f'user_notifications_{request.user.id}')
                cache.delete(f'notification_count_{request.user.id}')
                return Response({"status": "success", "count": updated})
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    list=extend_schema(
        description="List all notification types",
        summary="List Notification Types",
        tags=["Notifications"],
    )
)
class NotificationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationType.objects.all().order_by("name")
    serializer_class = NotificationTypeSerializer

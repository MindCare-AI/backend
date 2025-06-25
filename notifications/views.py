# notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.core.cache import cache
from rest_framework.pagination import LimitOffsetPagination
from .models import Notification, NotificationType
from .serializers import (
    NotificationSerializer,
    NotificationTypeSerializer,
    NotificationUpdateSerializer,
    BulkDeleteNotificationSerializer,
)
import logging

logger = logging.getLogger(__name__)


class NotificationPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    http_method_names = [
        "get",
        "post",
        "patch",
        "head",
        "options",
    ]  # Ensure "post" is included

    def get_queryset(self):
        """Get notifications for the current user with type information and caching."""
        cache_key = f"user_notifications_{self.request.user.id}"
        queryset = cache.get(cache_key)

        if queryset is None:
            queryset = (
                Notification.objects.filter(user=self.request.user)
                .select_related("notification_type")
                .order_by("-created_at")
            )
            cache.set(cache_key, queryset, timeout=300)  # Cache for 5 minutes

        # Add filtering for read/unread
        read_param = self.request.query_params.get("read", None)
        if read_param is not None:
            is_read = read_param.lower() == "true"
            # We need to create a new queryset for filtering since we got it from cache
            # This ensures we don't modify the cached queryset
            queryset = queryset.filter(read=is_read)

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list method to use pagination"""
        queryset = self.filter_queryset(self.get_queryset())

        # Check if pagination is needed
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If no pagination requested, return all results
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
                    cache.delete(f"user_notifications_{request.user.id}")
                    cache.delete(f"notification_count_{request.user.id}")
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
                    "unread_count": {"type": "integer"},
                    "total_count": {"type": "integer"},
                },
            }
        },
    )
    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        """Return counts of notifications"""
        user = request.user

        # Get counts - using 'user' instead of 'recipient'
        unread_count = self.get_queryset().filter(user=user, read=False).count()

        total_count = self.get_queryset().filter(user=user).count()

        return Response({"unread_count": unread_count, "total_count": total_count})

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
                updated = request.user.notifications.filter(read=False).update(
                    read=True
                )
                # Invalidate user's notification cache
                cache.delete(f"user_notifications_{request.user.id}")
                cache.delete(f"notification_count_{request.user.id}")
                return Response({"status": "success", "count": updated})
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Delete multiple notifications at once",
        request=BulkDeleteNotificationSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "deleted_count": {"type": "integer"},
                    "notification_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
            },
        },
    )
    @action(detail=False, methods=["post", "get", "options"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """Delete multiple notifications at once"""
        # For GET requests, just return the form - don't return 405
        if request.method == "GET":
            serializer = BulkDeleteNotificationSerializer()
            return Response({"notification_ids": []})

        serializer = BulkDeleteNotificationSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        notification_ids = serializer.validated_data["notification_ids"]

        try:
            with transaction.atomic():
                notifications = Notification.objects.filter(
                    user=request.user, id__in=notification_ids
                )

                count = notifications.count()
                notifications.delete()

                # Cache invalidation
                cache.delete(f"user_notifications_{request.user.id}")
                cache.delete(f"notification_count_{request.user.id}")

                return Response(
                    {
                        "message": f"{count} notifications deleted successfully",
                        "deleted_count": count,
                        "notification_ids": notification_ids,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error(f"Error bulk deleting notifications: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
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

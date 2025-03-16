# notifications/views.py
import logging
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_view
from django.db import transaction
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer, NotificationUpdateSerializer
from .permissions import IsNotificationOwner
from .services import NotificationService

notification_service = NotificationService()
logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List notifications with filtering options",
        summary="List Notifications",
        tags=["Notifications"],
    ),
    retrieve=extend_schema(
        description="Get a specific notification",
        summary="Get Notification",
        tags=["Notifications"],
    ),
)
class NotificationViewSet(
    viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsNotificationOwner]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get notifications with prefetch optimization"""
        return (
            Notification.objects.filter(user=self.request.user)
            .select_related("content_type", "user")
            .prefetch_related("action_object")
            .exclude(expires_at__lt=timezone.now())
            .order_by("-created_at")
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="priority",
                description="Filter by priority level",
                enum=["low", "normal", "high"],
            ),
            OpenApiParameter(
                name="unread",
                description="Filter unread notifications",
                required=False,
                type=bool,
            ),
            OpenApiParameter(
                name="type",
                description="Filter by notification type",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="since",
                description="Filter notifications since timestamp (ISO format)",
                required=False,
                type=str,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """List notifications with filtering"""
        try:
            queryset = self.get_queryset()

            # Apply filters
            if priority := request.query_params.get("priority"):
                queryset = queryset.filter(priority=priority)

            if (unread := request.query_params.get("unread")) is not None:
                if str(unread).lower() in ["true", "1"]:
                    queryset = queryset.filter(is_read=False)

            if notification_type := request.query_params.get("type"):
                queryset = queryset.filter(notification_type=notification_type)

            if since := request.query_params.get("since"):
                try:
                    since_date = timezone.parse_datetime(since)
                    queryset = queryset.filter(created_at__gte=since_date)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format for 'since' parameter"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error listing notifications: {str(e)}")
            return Response(
                {"error": "Failed to retrieve notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["patch"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Optimized bulk read update"""
        try:
            with transaction.atomic():
                updated = request.user.notifications.filter(is_read=False).update(
                    is_read=True, read_at=timezone.now()
                )
            return Response({"marked_read": updated})
        except Exception as e:
            logger.error(f"Bulk read error: {str(e)}")
            return Response(
                {"error": "Failed to update notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = request.user.notifications.filter(is_read=False).count()
        return Response({"unread_count": count})

    @extend_schema(request=NotificationUpdateSerializer)
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = NotificationUpdateSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        description="Mark multiple notifications as read",
        request={"application/json": {"ids": ["array", "integer"]}},
        responses={200: {"marked_read": "integer"}},
    )
    @action(detail=False, methods=["post"])
    def mark_multiple_read(self, request):
        try:
            with transaction.atomic():
                notification_ids = request.data.get("ids", [])
                if not notification_ids:
                    return Response(
                        {"error": "No notification IDs provided"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                updated = Notification.objects.filter(
                    id__in=notification_ids, user=request.user
                ).update(is_read=True, read_at=timezone.now())

                return Response({"marked_read": updated})

        except Exception as e:
            logger.error(f"Error marking notifications read: {str(e)}")
            return Response(
                {"error": "Failed to update notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Delete all read notifications",
        responses={200: {"deleted": "integer"}},
    )
    @action(detail=False, methods=["delete"])
    def clear_all(self, request):
        try:
            with transaction.atomic():
                deleted = request.user.notifications.filter(is_read=True).delete()[0]
                return Response({"deleted": deleted})
        except Exception as e:
            logger.error(f"Error clearing notifications: {str(e)}")
            return Response(
                {"error": "Failed to clear notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Get notification statistics",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "unread_count": {"type": "integer"},
                    "total_count": {"type": "integer"},
                    "newest_notification": {"type": "string", "format": "date-time"},
                },
            }
        },
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        try:
            queryset = self.get_queryset()
            stats = {
                "unread_count": queryset.filter(is_read=False).count(),
                "total_count": queryset.count(),
                "newest_notification": queryset.values_list(
                    "created_at", flat=True
                ).first(),
            }
            return Response(stats)
        except Exception as e:
            logger.error(f"Error getting notification stats: {str(e)}")
            return Response(
                {"error": "Failed to retrieve notification stats"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def send_test(self, request):
        """Test notification creation (staff only)"""
        if not request.user.is_staff:
            return Response(
                {"error": "Staff access required"}, status=status.HTTP_403_FORBIDDEN
            )
        try:
            notification = notification_service.create_notification(
                user=request.user, message="Test notification", notification_type="test"
            )
            return Response(
                {"status": "notification sent", "notification_id": notification.id}
            )
        except Exception as e:
            logger.error(f"Error creating test notification: {str(e)}")
            return Response(
                {"error": "Failed to create test notification"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

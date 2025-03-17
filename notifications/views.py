# notifications/views.py
import logging
from django.utils import timezone
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from templated_email import send_templated_mail
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import Notification
from users.models.preferences import UserPreferences
from .serializers import (
    NotificationSerializer,
    NotificationBulkActionSerializer,
    NotificationCountSerializer,
    MarkAllReadSerializer,
)
from users.serializers.preferences import UserPreferencesSerializer
from .services import NotificationService
from .services.cache_service import NotificationCacheService
from typing import Any, List
from django.db.models.query import QuerySet
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from .filters import NotificationFilter
from drf_spectacular.utils import extend_schema, extend_schema_view
from users.permissions.user import IsSuperUserOrSelf  # Added import

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationRateThrottle(UserRateThrottle):
    rate = "60/minute"


@extend_schema_view(
    get=extend_schema(
        summary="List Notifications",
        description="Retrieve a list of notifications for the authenticated user.",
    )
)
class NotificationListView(generics.ListAPIView):
    """
    Retrieve a list of notifications for the authenticated user.
    """

    permission_classes = [IsAuthenticated, IsSuperUserOrSelf]  # Updated permissions
    serializer_class = NotificationSerializer
    throttle_classes = [NotificationRateThrottle]
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotificationFilter

    def get_queryset(self) -> QuerySet:
        """
        Optionally restricts the returned notifications by filtering against
        query parameters in the URL.
        """
        try:
            # Include query parameters into the cache key to avoid stale/incorrect data.
            unread_only = self.request.query_params.get("unread", False)
            limit = self.request.query_params.get("limit")
            offset = self.request.query_params.get("offset", 0)
            cache_key = f"user_notifications_{self.request.user.id}_{unread_only}_{limit}_{offset}"

            notification_ids = cache.get(cache_key)
            if not notification_ids:
                queryset = (
                    NotificationService.get_notifications(
                        user=self.request.user,
                        limit=int(limit) if limit else None,
                        offset=int(offset),
                        unread_only=unread_only,
                    )
                    .select_related("notification_type")
                    .order_by("-priority", "-created_at")
                )

                notification_ids = list(queryset.values_list("id", flat=True))
                cache.set(cache_key, notification_ids, 300)  # Cache for 5 minutes

            return Notification.objects.filter(id__in=notification_ids).select_related(
                "notification_type"
            )
        except Exception as e:
            logger.error(f"Error fetching notifications: {e}")
            return Notification.objects.none()


@extend_schema_view(
    patch=extend_schema(
        summary="Mark Single Notification as Read",
        description="Mark a single notification as read for the authenticated user.",
    )
)
class MarkNotificationReadView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    http_method_names = ["patch"]

    def get_queryset(self):
        # Ensure the user can only update their own notifications
        return Notification.objects.filter(user=self.request.user)

    def patch(self, request, *args, **kwargs):
        try:
            notification = self.get_object()
            notification.mark_as_read()
            NotificationCacheService.invalidate_cache(
                request.user.id
            )  # invalidate cache
            return Response(status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception:
            logger.exception("Error marking notification as read")
            return Response(
                {"detail": "Failed to mark as read."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        summary="Mark All Notifications as Read",
        description="Mark all notifications as read for the authenticated user.",
    )
)
class MarkAllNotificationsReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MarkAllReadSerializer  # Now properly defined and imported

    def post(self, request):
        try:
            Notification.objects.filter(user=request.user, is_read=False).update(
                is_read=True, read_at=timezone.now()
            )
            NotificationCacheService.invalidate_cache(request.user.id)
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Error marking all notifications as read for user {request.user.id}: {e}"
            )
            return Response(
                {"detail": "Failed to mark all notifications as read."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    summary="Notification Preferences",
    description="Retrieve and update notification preferences for the authenticated user.",
)
class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserPreferencesSerializer

    def get_object(self):
        return UserPreferences.objects.get_or_create(user=self.request.user)[0]


@extend_schema(
    summary="Notification Count",
    description="Retrieve total count, unread count, and unread count by category for the user.",
)
class NotificationCountView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationCountSerializer

    def get_object(self):
        user = self.request.user
        total = Notification.objects.filter(user=user).count()
        unread = Notification.objects.filter(user=user, is_read=False).count()
        unread_by_category = Notification.get_unread_count_by_category(user)
        # Convert list of dicts into a dictionary
        unread_by_category_dict = {
            item["category"]: item["count"] for item in unread_by_category
        }
        return {
            "total": total,
            "unread": unread,
            "unread_by_category": unread_by_category_dict,
        }


@extend_schema_view(
    post=extend_schema(
        summary="Bulk Notification Action",
        description="Perform bulk actions like mark as read, delete, or archive on notifications.",
    )
)
class NotificationBulkActionView(generics.GenericAPIView):
    """
    Perform bulk actions on notifications such as mark as read, delete, or archive.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationBulkActionSerializer

    def post(self, request: Any) -> Response:
        """
        Handle POST requests to perform bulk actions on notifications.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids: List[int] = serializer.validated_data["notification_ids"]
        action: str = serializer.validated_data["action"]

        try:
            if action == "mark_read":
                NotificationService.mark_as_read(ids, request.user)
            elif action == "delete":
                NotificationService.bulk_delete_notifications(ids, request.user)
            elif action == "archive":
                NotificationService.bulk_archive_notifications(ids, request.user)
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Bulk action '{action}' failed for user {request.user.id}: {e}"
            )
            return Response(
                {"detail": "Bulk action failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_list(request, category=None):
    """
    Retrieve a list of notifications for the authenticated user as JSON.
    """
    notifications = Notification.objects.filter(user=request.user)
    if category:
        notifications = notifications.filter(category=category)
    notifications = notifications.order_by("-priority", "-created_at")
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


def send_notification_email(user, template_name, context):
    send_templated_mail(
        template_name=template_name,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        context=context,
    )


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return redirect("login")
    else:
        # Invalid activation link
        return render(request, "activation_invalid.html")


class NotificationList(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

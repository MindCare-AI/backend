from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from typing import List, Optional, Dict, Any
from django.db.models import QuerySet
from ..models import Notification, NotificationPreference, NotificationType, User
import logging
from .websocket_service import WebSocketService
from .cache_service import NotificationCacheService
from .email_service import EmailService

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles notification operations centrally"""

    @staticmethod
    @transaction.atomic
    def mark_as_read(notification_ids: List[int], user: "User") -> None:
        try:
            updated = Notification.objects.filter(
                id__in=notification_ids, user=user, is_read=False
            ).update(is_read=True, read_at=timezone.now())
            logger.info("Marked %s notifications as read for user %s", updated, user.id)
            NotificationCacheService.invalidate_cache(user.id)
        except ValidationError as ve:
            logger.exception("Validation error in mark_as_read")
            raise ve
        except Exception as e:
            logger.exception("Error marking notifications as read")
            raise e

    @staticmethod
    @transaction.atomic
    def mark_as_unread(notification_ids: List[int], user: "User") -> None:
        try:
            updated = Notification.objects.filter(
                id__in=notification_ids, user=user, is_read=True
            ).update(is_read=False, read_at=None)
            logger.info(
                "Marked %s notifications as unread for user %s", updated, user.id
            )
            NotificationCacheService.invalidate_cache(user.id)
        except Exception as e:
            logger.exception("Error marking notifications as unread")
            raise e

    @staticmethod
    def get_notifications(
        user: "User",
        limit: Optional[int] = None,
        offset: int = 0,
        unread_only: bool = False,
        category: Optional[str] = None,
    ) -> QuerySet:
        queryset = Notification.objects.filter(user=user, is_archived=False)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        if category:
            queryset = queryset.filter(category=category)
        if limit:
            queryset = queryset[offset : offset + limit]
        return queryset.select_related("notification_type").order_by(
            "-priority", "-created_at"
        )

    @staticmethod
    @transaction.atomic
    def bulk_delete_notifications(notification_ids: List[int], user: "User") -> None:
        try:
            Notification.objects.filter(id__in=notification_ids, user=user).delete()
            NotificationCacheService.invalidate_cache(user.id)
        except Exception as e:
            logger.exception("Error deleting notifications")
            raise e

    @staticmethod
    @transaction.atomic
    def bulk_archive_notifications(notification_ids: List[int], user: "User") -> None:
        try:
            Notification.objects.filter(id__in=notification_ids, user=user).update(
                is_archived=True
            )
            NotificationCacheService.invalidate_cache(user.id)
        except Exception as e:
            logger.exception("Error archiving notifications")
            raise e

    @staticmethod
    def send_websocket_notification(user_id: int, notification: Notification) -> None:
        try:
            WebSocketService.send_websocket_notification(user_id, notification)
        except Exception as e:
            logger.exception("Error sending websocket notification")
            raise e

    @staticmethod
    def send_email_notification(notification: Notification) -> None:
        try:
            EmailService.send_notification_email(notification)
            logger.info(
                "Email notification sent successfully to %s", notification.user.email
            )
        except Exception as e:
            logger.exception("Error sending email notification")
            raise e


class UnifiedNotificationService:
    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        message: str,
        send_email: bool = False,
        send_in_app: bool = True,
        email_template: str = None,
        link: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = "medium",
        category: str = "general",
    ) -> Optional[Notification]:
        try:
            notification = None
            notification_type_obj, _ = NotificationType.objects.get_or_create(
                name=notification_type,
                defaults={
                    "description": f"Notification for {notification_type}",
                    "template_name": email_template,
                    "is_active": True,
                },
            )
            # Check user preferences for in-app notifications
            pref, _ = NotificationPreference.objects.get_or_create(user=user)
            if send_in_app and pref.in_app_notifications:
                notification = Notification.objects.create(
                    user=user,
                    notification_type=notification_type_obj,
                    title=title,
                    message=message,
                    link=link,
                    metadata=metadata or {},
                    priority=priority,
                    category=category,
                )
                # Trigger asynchronous websocket push.
                from ..tasks import send_websocket_notification_task

                send_websocket_notification_task.delay(user.id, notification.id)

            if send_email and pref.email_notifications:
                email_context = {
                    "title": title,
                    "message": message,
                    "link": link,
                    "metadata": metadata,
                }
                EmailService.send_email(
                    user=user,
                    template_name=email_template
                    or "notifications/default_notification.html",
                    context=email_context,
                )
                # Update flag if email was sent
                if notification:
                    notification.email_sent = True
                    notification.save()
            return notification
        except Exception as e:
            logger.exception("Failed to send notification")
            raise e

# notifications/services/unified_service.py
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings
from django.db.models import QuerySet
import logging
from typing import List, Optional, Dict, Any

from users.models.preferences import UserPreferences
from ..models import Notification, NotificationType, User
from templated_email import send_templated_mail
from .websocket_service import WebSocketService
from .cache_service import NotificationCacheService
from .email_service import EmailService

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles notification operations"""

    @staticmethod
    @transaction.atomic
    def mark_as_read(notification_ids: List[int], user: "User") -> None:
        try:
            updated = Notification.objects.filter(
                id__in=notification_ids, user=user, is_read=False
            ).update(is_read=True, read_at=timezone.now())
            logger.info(f"Marked {updated} notifications as read for user {user.id}")
            NotificationCacheService.invalidate_cache(user.id)  # <-- invalidate cache
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            raise

    @staticmethod
    def get_notifications(
        user: "User",
        limit: Optional[int] = None,
        offset: int = 0,
        unread_only: bool = False,
        category: Optional[str] = None,
    ) -> "QuerySet":
        queryset = Notification.objects.filter(user=user)

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
            NotificationCacheService.invalidate_cache(user.id)  # <-- invalidate cache
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Error deleting notifications: {str(e)}")
            raise

    @staticmethod
    @transaction.atomic
    def bulk_archive_notifications(notification_ids: List[int], user: "User") -> None:
        try:
            Notification.objects.filter(id__in=notification_ids, user=user).update(
                is_archived=True
            )
            NotificationCacheService.invalidate_cache(user.id)  # <-- invalidate cache
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Error archiving notifications: {str(e)}")
            raise

    @staticmethod
    def send_websocket_notification(user_id: int, notification: Notification) -> None:
        WebSocketService.send_websocket_notification(user_id, notification)

    @staticmethod
    def send_email_notification(notification: Notification) -> None:
        """Send email using SMTP with error handling"""
        try:
            context = {
                "notification": notification,
                "recipient_name": notification.user.get_full_name()
                or notification.user.username,
                "site_url": settings.SITE_URL,
            }

            if not all(
                [settings.EMAIL_HOST, settings.EMAIL_PORT, settings.DEFAULT_FROM_EMAIL]
            ):
                raise ValidationError("Email settings are not properly configured")

            send_templated_mail(
                template_name=notification.notification_type.template_name,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                context=context,
                fail_silently=False,
            )
            logger.info(
                f"Email notification sent successfully to {notification.user.email}"
            )
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            raise


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

            # Use UserPreferences
            preferences = UserPreferences.objects.get_or_create(user=user)[0]

            # Check if notification type is disabled by the user
            disabled_types = preferences.disabled_notification_types.all()
            if notification_type in disabled_types:
                logger.debug(f"Notification type {notification_type} disabled by user")
                return None

            if send_in_app:
                # Check user preferences for in-app notifications
                if preferences.in_app_notifications:
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
                    from ..tasks import send_websocket_notification_task

                    send_websocket_notification_task.delay(user.id, notification.id)

            if send_email:
                # Check user preferences for email notifications
                if preferences.email_notifications:
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
                    if notification:
                        notification.email_sent = True
                        notification.save()
            return notification
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            raise

# notifications/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from notifications.services import EmailService
from notifications.models import Notification
from typing import Tuple, Optional
from django.core.cache import cache
import logging
from .models import Notification
from .services.email_service import EmailService
from .services.websocket_service import WebSocketService

logger = logging.getLogger(__name__)


@shared_task(
    name="notifications.send_email",
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    priority=10,
)
def send_notification_email(notification_id: int) -> None:
    """
    Send an email notification asynchronously.

    Args:
        notification_id: ID of the notification to send

    Raises:
        Notification.DoesNotExist: If notification with given ID is not found
        send_notification_email.retry: If email sending fails
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        EmailService.send_email(
            user=notification.user,
            template_name=notification.notification_type.template_name
            or "notifications/default_notification.html",
            context={
                "message": notification.message,
                "title": notification.title,
                "link": notification.link,
            },
        )
    except Notification.DoesNotExist:
        logger.error("Notification %s not found", notification_id)
    except Exception as exc:
        logger.exception("Failed to send notification email for %s", notification_id)
        raise send_notification_email.retry(exc=exc)


@shared_task(
    name="notifications.cleanup_old",
    ignore_result=True,
    priority=5,
)
def cleanup_old_notifications(days: int = 30) -> Optional[Tuple[int, dict]]:
    """
    Remove old read notifications to prevent database bloat.

    Args:
        days: Number of days after which to delete read notifications

    Returns:
        Tuple containing count of deleted objects and a dict with details,
        or None if deletion fails
    """
    try:
        cutoff = timezone.now() - timedelta(days=days)
        deleted = Notification.objects.filter(
            created_at__lt=cutoff, is_read=True
        ).delete()
        logger.info("Cleaned up %s old notifications", deleted[0])
        return deleted
    except Exception:
        logger.exception("Cleanup task failed")
        return None


@shared_task(
    name="notifications.send_websocket_notification_task",
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    priority=10,
)
def send_websocket_notification_task(user_id: int, notification_id: int) -> None:
    """
    Send a WebSocket notification asynchronously.

    Args:
        user_id: ID of the user to send the notification to
        notification_id: ID of the notification to send

    Raises:
        Notification.DoesNotExist: If notification with given ID is not found
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        WebSocketService.send_websocket_notification(user_id, notification)
    except Notification.DoesNotExist:
        logger.error("Notification %s not found", notification_id)
    except Exception as exc:
        logger.exception(
            "Failed to send websocket notification for %s", notification_id
        )
        raise send_websocket_notification_task.retry(exc=exc)


def invalidate_notification_cache(user_id):
    cache_key = f"user_notifications_{user_id}"
    cache.delete(cache_key)

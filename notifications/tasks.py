# notifications/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from .models import Notification

logger = logging.getLogger(__name__)

@shared_task(
    autoretry_for=(Exception,), 
    max_retries=3,
    retry_backoff=30
)
def cleanup_old_notifications(days=30):
    """Configurable notification cleanup"""
    try:
        cutoff = timezone.now() - timezone.timedelta(days=days)
        deleted_count = Notification.objects.filter(
            Q(expires_at__lt=timezone.now()) | 
            Q(created_at__lt=cutoff, is_read=True)
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise
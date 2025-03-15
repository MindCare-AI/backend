#notifications/tasks.py
from celery import shared_task
from .services import NotificationService


@shared_task
def cleanup_old_notifications():
    """Periodic task to clean up old notifications"""
    service = NotificationService()
    return service.delete_old_notifications()

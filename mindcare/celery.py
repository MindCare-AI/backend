#mindcare/celery.py
import os
from celery import Celery
from celery.schedules import crontab  # <-- Import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mindcare.settings")

app = Celery("mindcare")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "cleanup-notifications": {
        "task": "notifications.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        "kwargs": {"days": 30},
    },
}

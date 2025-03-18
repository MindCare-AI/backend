# notifications/apps.py
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    name = 'notifications'
    verbose_name = 'Notifications Management'

    def ready(self):
        import notifications.signals  #noqa

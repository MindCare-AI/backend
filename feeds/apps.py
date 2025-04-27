from django.apps import AppConfig


class FeedsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feeds'
    
    def ready(self):
        """Import signal handlers when the app is ready"""
        import feeds.signals  # noqa

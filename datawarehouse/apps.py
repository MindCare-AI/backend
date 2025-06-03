# datawarehouse/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class DatawarehouseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "datawarehouse"
    verbose_name = "MindCare Data Warehouse"

    def ready(self):
        """Initialize data warehouse services when app is ready"""
        try:
            # Import and initialize the data collection service

            # Start background monitoring (if configured)
            if hasattr(self, "start_monitoring"):
                self.start_monitoring()

            logger.info("Data Warehouse app initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Data Warehouse app: {str(e)}")

    def start_monitoring(self):
        """Start data quality monitoring services"""
        # This would be called in production to start monitoring
        pass

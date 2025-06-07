# AI_engine/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from mood.models import MoodLog
from journal.models import JournalEntry
from .services.ai_analysis import ai_service
from .services.data_interface import ai_data_interface
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MoodLog)
def trigger_mood_analysis(sender, instance, created, **kwargs):
    """Trigger AI analysis when a new mood log is created using AI data interface"""
    if created:
        try:
            # Check data quality before triggering analysis
            dataset = ai_data_interface.get_ai_ready_dataset(instance.user.id, 7)
            quality_metrics = dataset.get("quality_metrics", {})

            # Only trigger analysis if there's sufficient data quality
            if quality_metrics.get("overall_quality", 0.0) > 0.2:
                analysis = ai_service.analyze_user_data(instance.user, date_range=7)

                if analysis:
                    logger.info(
                        f"Generated new AI analysis for user {instance.user.id} after mood log. "
                        f"Recommendations created: {analysis.get('recommendations_created', 0)}, "
                        f"Data quality: {quality_metrics.get('overall_quality', 0.0):.2f}, "
                        f"Data sources: {', '.join(dataset.get('data_sources', []))}"
                    )
            else:
                logger.debug(
                    f"Skipped analysis for user {instance.user.id} - insufficient data quality: "
                    f"{quality_metrics.get('overall_quality', 0.0):.2f}"
                )

        except Exception as e:
            logger.error(f"Error triggering mood analysis: {str(e)}", exc_info=True)


@receiver(post_save, sender=JournalEntry)
def trigger_journal_analysis(sender, instance, created, **kwargs):
    """Trigger AI analysis when a new journal entry is created using AI data interface"""
    if created:
        try:
            # Check data quality before triggering analysis
            dataset = ai_data_interface.get_ai_ready_dataset(instance.user.id, 7)
            quality_metrics = dataset.get("quality_metrics", {})

            # Only trigger analysis if there's sufficient data quality
            if quality_metrics.get("overall_quality", 0.0) > 0.2:
                analysis = ai_service.analyze_user_data(instance.user, date_range=7)

                if analysis:
                    logger.info(
                        f"Generated new AI analysis for user {instance.user.id} after journal entry. "
                        f"Recommendations created: {analysis.get('recommendations_created', 0)}, "
                        f"Data quality: {quality_metrics.get('overall_quality', 0.0):.2f}, "
                        f"Data sources: {', '.join(dataset.get('data_sources', []))}"
                    )
            else:
                logger.debug(
                    f"Skipped analysis for user {instance.user.id} - insufficient data quality: "
                    f"{quality_metrics.get('overall_quality', 0.0):.2f}"
                )

        except Exception as e:
            logger.error(f"Error triggering journal analysis: {str(e)}", exc_info=True)

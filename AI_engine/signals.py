#AI_engine/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from mood.models import MoodLog
from journal.models import JournalEntry
from .services import AIAnalysisService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MoodLog)
def trigger_mood_analysis(sender, instance, created, **kwargs):
    """Trigger AI analysis when a new mood log is created"""
    if created:
        try:
            service = AIAnalysisService()
            analysis = service.analyze_user_data(
                instance.user, date_range=7
            )  # Analyze last week

            if analysis:
                logger.info(
                    f"Generated new AI analysis for user {instance.user.id} after mood log"
                )

        except Exception as e:
            logger.error(f"Error triggering mood analysis: {str(e)}", exc_info=True)


@receiver(post_save, sender=JournalEntry)
def trigger_journal_analysis(sender, instance, created, **kwargs):
    """Trigger AI analysis when a new journal entry is created"""
    if created:
        try:
            service = AIAnalysisService()
            analysis = service.analyze_user_data(
                instance.user, date_range=7
            )  # Analyze last week

            if analysis:
                logger.info(
                    f"Generated new AI analysis for user {instance.user.id} after journal entry"
                )

        except Exception as e:
            logger.error(f"Error triggering journal analysis: {str(e)}", exc_info=True)

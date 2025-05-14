from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from notifications.services import UnifiedNotificationService
from .models import JournalEntry
from AI_engine.services import predictive_service
from AI_engine.models import AIInsight
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=JournalEntry)
def handle_journal_entry_save(sender, instance, created, **kwargs):
    """Handle notifications when journal entries are created or updated"""
    try:
        notification_service = UnifiedNotificationService()
        user = instance.user

        if created:
            # Notify user about successful journal creation
            notification_service.send_notification(
                user=user,
                notification_type_name="journal_created",
                title="New Journal Entry Created",
                message=f"Your journal entry from {instance.created_at.strftime('%Y-%m-%d')} has been created.",
                metadata={
                    "entry_id": str(instance.id),
                    "created_at": timezone.now().isoformat(),
                },
                send_email=False,
                send_in_app=True,
                priority="low",
            )
        elif instance.shared_with_therapist:
            # Notify therapist when entry is shared with them
            if hasattr(user, "patient_profile") and user.patient_profile.therapist:
                therapist = user.patient_profile.therapist.user
                notification_service.send_notification(
                    user=therapist,
                    notification_type_name="journal_shared",
                    title="New Journal Entry Shared",
                    message=f"Patient {user.get_full_name()} has shared a journal entry with you.",
                    metadata={
                        "entry_id": str(instance.id),
                        "patient_id": str(user.id),
                        "shared_at": timezone.now().isoformat(),
                    },
                    send_email=True,
                    send_in_app=True,
                    priority="medium",
                )

    except Exception as e:
        logger.error(f"Error handling journal entry signal: {str(e)}", exc_info=True)


@receiver(post_delete, sender=JournalEntry)
def handle_journal_entry_delete(sender, instance, **kwargs):
    """Handle cleanup when journal entries are deleted"""
    try:
        # Notify user about journal deletion
        notification_service = UnifiedNotificationService()
        notification_service.send_notification(
            user=instance.user,
            notification_type_name="journal_deleted",
            title="Journal Entry Deleted",
            message=f"Your journal entry '{instance.title}' has been deleted.",
            metadata={
                "deleted_at": timezone.now().isoformat(),
            },
            send_email=False,
            send_in_app=True,
            priority="low",
        )

    except Exception as e:
        logger.error(f"Error handling journal delete signal: {str(e)}", exc_info=True)


@receiver(post_save, sender=JournalEntry)
def analyze_journal_entry(sender, instance, created, **kwargs):
    """Trigger AI analysis when new journal entry is created or content changed"""
    # Check if this is a new entry or if content was modified
    update_fields = kwargs.get("update_fields", []) or []  # Handle None case

    if created or (not created and "content" in update_fields):
        try:
            # Analyze journal patterns
            analysis = predictive_service.analyze_journal_patterns(instance.user)
            # Ensure analysis is a dict; if it's a string, try to parse it as JSON
            if isinstance(analysis, str):
                import json

                try:
                    analysis = json.loads(analysis)
                except Exception:
                    logger.error(f"Failed to parse analysis string: {analysis}")
                    analysis = {}

            # If analysis is None, initialize as empty dict
            if analysis is None:
                analysis = {}

            # If concerns exist AND they are not None/empty, create an insight
            if analysis.get("concerns") and analysis.get("concerns") not in [None, []]:
                AIInsight.objects.create(
                    user=instance.user,
                    insight_type="journal_theme",
                    insight_data={
                        "analysis": analysis,
                        "journal_entry_id": str(instance.id),
                    },
                    priority="medium",
                )

            # Update therapy predictions if themes indicate significant changes
            if analysis.get("sentiment_trend") in ["improving", "declining"]:
                therapy_prediction = predictive_service.predict_therapy_outcomes(
                    instance.user
                )
                if (
                    therapy_prediction
                    and therapy_prediction.get("predicted_outcome") == "declining"
                ):
                    AIInsight.objects.create(
                        user=instance.user,
                        insight_type="therapy_adjustment",
                        insight_data={
                            "prediction": therapy_prediction,
                            "context": "Journal sentiment change",
                        },
                        priority="high",
                    )

        except Exception as e:
            logger.error(f"Error analyzing journal patterns: {str(e)}")

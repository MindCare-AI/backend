from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from journal.models import JournalEntry
from notifications.services import UnifiedNotificationService
from django.utils import timezone
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
                message=f"Your journal entry '{instance.title}' has been created.",
                metadata={
                    "entry_id": str(instance.id),
                    "created_at": timezone.now().isoformat(),
                },
                send_email=False,
                send_in_app=True,
                priority="low"
            )
        elif instance.shared_with_therapist:
            # Notify therapist when entry is shared with them
            if hasattr(user, 'patient_profile') and user.patient_profile.therapist:
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
                    priority="medium"
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
            priority="low"
        )

    except Exception as e:
        logger.error(f"Error handling journal delete signal: {str(e)}", exc_info=True)

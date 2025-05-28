from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from notifications.services import UnifiedNotificationService
from .models import Appointment
from AI_engine.services import predictive_service, therapy_analysis_service
import logging

logger = logging.getLogger(__name__)
notification_service = UnifiedNotificationService()


@receiver(post_save, sender=Appointment)
def appointment_notification_handler(sender, instance, created, **kwargs):
    """Handle notifications for appointment events"""
    try:
        if created:
            # Notify therapist of new appointment request
            notification_service.send_notification(
                user=instance.therapist.user,
                notification_type_name="appointment_request",
                title="New Appointment Request",
                message=f"New appointment request from {instance.patient.user.get_full_name()} for {instance.appointment_date.strftime('%B %d, %Y at %I:%M %p')}",
                metadata={
                    "appointment_id": str(instance.id),
                    "patient_id": str(instance.patient.user.id),
                    "appointment_date": instance.appointment_date.isoformat(),
                    "status": instance.status,
                },
                send_email=True,
                send_in_app=True,
                priority="medium",
            )

            # Notify patient of appointment request confirmation
            notification_service.send_notification(
                user=instance.patient.user,
                notification_type_name="appointment_requested",
                title="Appointment Request Submitted",
                message=f"Your appointment request with {instance.therapist.user.get_full_name()} for {instance.appointment_date.strftime('%B %d, %Y at %I:%M %p')} has been submitted",
                metadata={
                    "appointment_id": str(instance.id),
                    "therapist_id": str(instance.therapist.user.id),
                    "appointment_date": instance.appointment_date.isoformat(),
                    "status": instance.status,
                },
                send_email=True,
                send_in_app=True,
                priority="medium",
            )
        else:
            old_instance = Appointment.objects.get(pk=instance.pk)

            # Status change notifications
            if old_instance.status != instance.status:
                if instance.status == "confirmed":
                    # Notify patient of confirmation
                    notification_service.send_notification(
                        user=instance.patient.user,
                        notification_type_name="appointment_confirmed",
                        title="Appointment Confirmed",
                        message=f"Your appointment with {instance.therapist.user.get_full_name()} for {instance.appointment_date.strftime('%B %d, %Y at %I:%M %p')} has been confirmed",
                        metadata={
                            "appointment_id": str(instance.id),
                            "appointment_date": instance.appointment_date.isoformat(),
                            "video_session_link": instance.video_session_link,
                        },
                        send_email=True,
                        send_in_app=True,
                        priority="high",
                    )
                elif instance.status == "rescheduled":
                    # Notify affected party about reschedule
                    affected_user = (
                        instance.patient.user
                        if instance.rescheduled_by == instance.therapist.user
                        else instance.therapist.user
                    )
                    notification_service.send_notification(
                        user=affected_user,
                        notification_type_name="appointment_rescheduled",
                        title="Appointment Rescheduled",
                        message=f"Your appointment has been rescheduled to {instance.appointment_date.strftime('%B %d, %Y at %I:%M %p')}",
                        metadata={
                            "appointment_id": str(instance.id),
                            "old_date": old_instance.appointment_date.isoformat(),
                            "new_date": instance.appointment_date.isoformat(),
                            "rescheduled_by": instance.rescheduled_by.get_full_name(),
                        },
                        send_email=True,
                        send_in_app=True,
                        priority="high",
                    )
                elif instance.status == "cancelled":
                    # Notify affected party about cancellation
                    affected_user = (
                        instance.patient.user
                        if instance.cancelled_by == instance.therapist.user
                        else instance.therapist.user
                    )
                    notification_service.send_notification(
                        user=affected_user,
                        notification_type_name="appointment_cancelled",
                        title="Appointment Cancelled",
                        message=f"Your appointment for {instance.appointment_date.strftime('%B %d, %Y at %I:%M %p')} has been cancelled",
                        metadata={
                            "appointment_id": str(instance.id),
                            "cancelled_by": instance.cancelled_by.get_full_name(),
                            "cancellation_reason": instance.cancellation_reason,
                        },
                        send_email=True,
                        send_in_app=True,
                        priority="high",
                    )

    except Exception as e:
        logger.error(
            f"Error in appointment notification handler: {str(e)}", exc_info=True
        )


@receiver(pre_save, sender=Appointment)
def appointment_reminder_handler(sender, instance, **kwargs):
    """Set up appointment reminders"""
    try:
        if (
            instance.pk is None or instance.status == "confirmed"
        ):  # New or confirmed appointment
            reminder_times = [(24, "day"), (1, "hour")]

            for hours, unit in reminder_times:
                reminder_date = instance.appointment_date - timedelta(hours=hours)
                if reminder_date > timezone.now():
                    notification_service.send_notification(
                        user=instance.patient.user,
                        notification_type_name="appointment_reminder",
                        title=f"Appointment Reminder - {unit}",
                        message=f"Reminder: Your appointment with {instance.therapist.user.get_full_name()} is in 1 {unit} at {instance.appointment_date.strftime('%I:%M %p')}",
                        metadata={
                            "appointment_id": str(instance.id),
                            "appointment_date": instance.appointment_date.isoformat(),
                            "video_session_link": instance.video_session_link,
                            "reminder_type": f"{unit}_before",
                        },
                        send_email=True,
                        send_in_app=True,
                        priority="medium",
                    )

                    # Also notify therapist
                    notification_service.send_notification(
                        user=instance.therapist.user,
                        notification_type_name="appointment_reminder",
                        title=f"Appointment Reminder - {unit}",
                        message=f"Reminder: Your appointment with {instance.patient.user.get_full_name()} is in 1 {unit} at {instance.appointment_date.strftime('%I:%M %p')}",
                        metadata={
                            "appointment_id": str(instance.id),
                            "appointment_date": instance.appointment_date.isoformat(),
                            "video_session_link": instance.video_session_link,
                            "reminder_type": f"{unit}_before",
                        },
                        send_email=True,
                        send_in_app=True,
                        priority="medium",
                    )

    except Exception as e:
        logger.error(f"Error in appointment reminder handler: {str(e)}", exc_info=True)


@receiver(post_save, sender=Appointment)
def analyze_appointment_data(sender, instance, created, **kwargs):
    """Analyze appointment data and generate insights"""
    if instance.status == "completed":
        try:
            # Analyze session notes if they exist
            if hasattr(instance, "session_notes"):
                analysis = therapy_analysis_service.analyze_session_notes(
                    instance.session_notes
                )

                if analysis.get("risk_factors"):
                    # Create high-priority insight for identified risks
                    from AI_engine.models import AIInsight

                    AIInsight.objects.create(
                        user=instance.patient,
                        insight_type="therapy_risk",
                        insight_data={
                            "analysis": analysis,
                            "appointment_id": str(instance.id),
                        },
                        priority="high",
                    )

            # Update therapy outcome predictions
            prediction = predictive_service.predict_therapy_outcomes(instance.patient)
            if prediction.get("predicted_outcome") == "declining":
                AIInsight.objects.create(
                    user=instance.patient,
                    insight_type="therapy_outcome",
                    insight_data={
                        "prediction": prediction,
                        "context": "Post-session analysis",
                    },
                    priority="medium",
                )

        except Exception as e:
            logger.error(f"Error analyzing appointment data: {str(e)}")


@receiver(pre_save, sender=Appointment)
def prepare_session_recommendations(sender, instance, **kwargs):
    """Generate AI recommendations before therapy session"""
    if instance.status == "scheduled" and not instance.ai_recommendations:
        try:
            recommendations = therapy_analysis_service.recommend_session_focus(
                instance.patient
            )
            instance.ai_recommendations = recommendations

        except Exception as e:
            logger.error(f"Error generating session recommendations: {str(e)}")


@receiver(post_save, sender="appointments.Appointment")
def analyze_for_upcoming_appointment(sender, instance, created, **kwargs):
    """Trigger therapy analysis when an appointment is scheduled"""
    if created and instance.status == "scheduled":
        try:
            # Analyze patient data for therapy session preparation
            analysis = therapy_analysis_service.analyze_for_therapy_session(
                user=instance.patient,
                days=7,  # Analyze last week of data
            )

            if analysis.get("success"):
                logger.info(
                    f"Generated therapy analysis for upcoming appointment {instance.id}"
                )
            else:
                logger.warning(
                    f"Therapy analysis failed for appointment {instance.id}: {analysis.get('message', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(
                f"Error in appointment therapy analysis: {str(e)}", exc_info=True
            )

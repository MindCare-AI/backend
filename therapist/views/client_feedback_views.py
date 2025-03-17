# therapist/views/client_feedback_views.py
from rest_framework import viewsets
from therapist.models.client_feedback import ClientFeedback
from therapist.serializers.client_feedback import ClientFeedbackSerializer
from notifications.services.unified_service import UnifiedNotificationService

class ClientFeedbackViewSet(viewsets.ModelViewSet):
    queryset = ClientFeedback.objects.all()
    serializer_class = ClientFeedbackSerializer

    def perform_create(self, serializer):
        # Save the feedback instance.
        instance = serializer.save()

        # Assuming the ClientFeedback model has a 'therapist' field with a related user,
        # send a notification to the therapist when new feedback is received.
        if hasattr(instance, 'therapist') and instance.therapist and hasattr(instance.therapist, 'user'):
            UnifiedNotificationService.send_notification(
                user=instance.therapist.user,
                notification_type="client_feedback",
                title="New Client Feedback Received",
                message=f"You have received new feedback from {getattr(instance, 'client', 'a client')}.",
                send_email=True,
                send_in_app=True,
                email_template="notifications/client_feedback.email",
                link=f"/feedback/{instance.id}/",
                priority="normal",
                category="feedback",
            )

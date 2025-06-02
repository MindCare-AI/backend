#AI_engine/services/crisis_monitoring.py
from typing import Dict, Any
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class CrisisMonitoringService:
    """Service for monitoring and responding to crisis situations"""

    def __init__(self):
        self.crisis_levels = {
            "low": 0.6,
            "medium": 0.75,
            "high": 0.85,
            "critical": 0.95,
        }

    def log_crisis_event(self, user, message: str, detection_data: Dict[str, Any]):
        """Log a crisis event for tracking and follow-up"""
        try:
            from ..models import CrisisEvent  # You'll need to create this model

            confidence = detection_data.get("confidence", 0)
            level = self._determine_crisis_level(confidence)

            crisis_event = CrisisEvent.objects.create(
                user=user,
                message_content=message[:500],  # Truncate for storage
                confidence=confidence,
                crisis_level=level,
                matched_terms=detection_data.get("matched_terms", []),
                category=detection_data.get("category"),
                timestamp=timezone.now(),
                resolved=False,
            )

            # Trigger appropriate responses based on level
            if level in ["high", "critical"]:
                self._trigger_immediate_response(user, crisis_event)

            return crisis_event

        except Exception as e:
            logger.error(f"Error logging crisis event: {str(e)}")
            return None

    def _determine_crisis_level(self, confidence: float) -> str:
        """Determine crisis level based on confidence score"""
        if confidence >= self.crisis_levels["critical"]:
            return "critical"
        elif confidence >= self.crisis_levels["high"]:
            return "high"
        elif confidence >= self.crisis_levels["medium"]:
            return "medium"
        else:
            return "low"

    def _trigger_immediate_response(self, user, crisis_event):
        """Trigger immediate response for high-risk situations"""
        try:
            # Send notifications to mental health staff
            from notifications.services import notification_service

            notification_service.send_notification(
                recipient_group="crisis_response_team",
                notification_type="crisis_alert",
                title=f"URGENT: Crisis Detected - User {user.username}",
                message="High-risk crisis content detected. Immediate attention required.",
                metadata={
                    "user_id": user.id,
                    "crisis_event_id": crisis_event.id,
                    "crisis_level": crisis_event.crisis_level,
                    "confidence": crisis_event.confidence,
                },
                priority="critical",
            )

            logger.critical(
                f"Crisis alert sent for user {user.id}, event {crisis_event.id}"
            )

        except Exception as e:
            logger.error(f"Error triggering immediate response: {str(e)}")


# Singleton instance
crisis_monitoring_service = CrisisMonitoringService()

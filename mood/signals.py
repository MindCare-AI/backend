#mood/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from AI_engine.services import predictive_service
from .models import MoodLog
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MoodLog)
def analyze_mood_patterns(sender, instance, created, **kwargs):
    """Trigger AI analysis when new mood log is created"""
    if created:
        try:
            # Predict potential mood declines
            prediction = predictive_service.predict_mood_decline(instance.user)

            # If high risk is detected, create an insight
            if prediction.get("risk_level") == "high":
                from AI_engine.models import AIInsight

                AIInsight.objects.create(
                    user=instance.user,
                    insight_type="mood_pattern",
                    insight_data={
                        "prediction": prediction,
                        "mood_log_id": str(instance.id),
                    },
                    priority="high",
                )
        except Exception as e:
            logger.error(f"Error analyzing mood patterns: {str(e)}")

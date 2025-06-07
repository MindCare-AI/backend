# AI_engine/services/data_interface.py
"""
Data Interface Service for AI_engine
Provides clean interface to datawarehouse, eliminating direct model access
"""

from typing import Dict, Any, List
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class AIDataInterfaceService:
    """
    Service that provides AI_engine with clean interface to datawarehouse
    Eliminates direct access to raw models (MoodLog, JournalEntry, etc.)
    """

    def __init__(self):
        self.datawarehouse_service = None
        self._initialize_datawarehouse()

    def _initialize_datawarehouse(self):
        """Initialize connection to datawarehouse services"""
        try:
            from datawarehouse.services.unified_data_collection_service import (
                unified_data_collector,
            )

            self.datawarehouse_service = unified_data_collector
            logger.info(
                "AI Data Interface Service initialized with datawarehouse connection"
            )
        except ImportError as e:
            logger.error(f"Failed to initialize datawarehouse connection: {e}")
            self.datawarehouse_service = None

    def get_ai_ready_dataset(
        self,
        user_id: int,
        period_days: int = 30,
        analysis_types: List[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Get AI-ready dataset for analysis

        Args:
            user_id: Target user ID
            period_days: Number of days to analyze
            analysis_types: Specific analysis types needed (mood, journal, etc.)
            use_cache: Whether to use cached datasets

        Returns:
            Comprehensive AI-ready dataset
        """
        if not self.datawarehouse_service:
            logger.error("Datawarehouse service not available")
            return self._create_empty_dataset(user_id, period_days)

        try:
            dataset = self.datawarehouse_service.get_ai_ready_dataset(
                user_id=user_id,
                date_range=period_days,
                analysis_types=analysis_types,
                use_cache=use_cache,
            )

            # Validate dataset quality
            if not self._validate_dataset_quality(dataset):
                logger.warning(f"Dataset quality check failed for user {user_id}")

            return dataset

        except Exception as e:
            logger.error(f"Error getting AI-ready dataset for user {user_id}: {e}")
            return self._create_empty_dataset(user_id, period_days)

    def get_mood_analytics(self, user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Get processed mood analytics for AI analysis
        Returns only mood-related data from datawarehouse
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["mood"])
            return dataset.get("mood_analytics", {})
        except Exception as e:
            logger.error(f"Error getting mood analytics for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_journal_analytics(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get processed journal analytics for AI analysis
        Returns only journal-related data from datawarehouse
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["journal"])
            return dataset.get("journal_analytics", {})
        except Exception as e:
            logger.error(f"Error getting journal analytics for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_behavioral_patterns(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get behavioral pattern analytics for AI analysis
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["behavior"])
            return dataset.get("behavioral_analytics", {})
        except Exception as e:
            logger.error(f"Error getting behavioral patterns for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_communication_metrics(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get communication metrics for AI analysis
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["communication"])
            return dataset.get("communication_analytics", {})
        except Exception as e:
            logger.error(f"Error getting communication metrics for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_therapy_session_data(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get therapy session analytics for AI analysis
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["therapy"])
            return dataset.get("therapy_session_analytics", {})
        except Exception as e:
            logger.error(f"Error getting therapy session data for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_social_engagement_data(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get social engagement analytics for AI analysis
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, ["social"])
            return dataset.get("social_analytics", {})
        except Exception as e:
            logger.error(
                f"Error getting social engagement data for user {user_id}: {e}"
            )
            return {"status": "error", "error": str(e)}

    def get_cross_domain_insights(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get cross-domain insights and correlations
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days)
            return dataset.get("processed_insights", {})
        except Exception as e:
            logger.error(f"Error getting cross-domain insights for user {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_data_quality_metrics(
        self, user_id: int, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get data quality metrics for the user's dataset
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days)
            quality_metrics = dataset.get("quality_metrics", {})

            return {
                "overall_quality": quality_metrics.get("overall_quality", 0.0),
                "completeness": quality_metrics.get("completeness", 0.0),
                "domain_scores": quality_metrics.get("domain_scores", {}),
                "readiness_flags": quality_metrics.get("readiness_flags", {}),
                "analysis_recommendation": quality_metrics.get(
                    "analysis_recommendation", "insufficient"
                ),
            }
        except Exception as e:
            logger.error(f"Error getting data quality metrics for user {user_id}: {e}")
            return {"overall_quality": 0.0, "completeness": 0.0, "error": str(e)}

    def check_analysis_readiness(
        self, user_id: int, analysis_type: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Check if user has sufficient data for specific analysis type

        Args:
            user_id: Target user ID
            analysis_type: Type of analysis (mood, journal, behavior, etc.)
            period_days: Analysis period

        Returns:
            Readiness assessment with recommendations
        """
        try:
            quality_metrics = self.get_data_quality_metrics(user_id, period_days)
            readiness_flags = quality_metrics.get("readiness_flags", {})

            analysis_key = f"ready_for_{analysis_type}_analysis"
            is_ready = readiness_flags.get(analysis_key, False)

            result = {
                "is_ready": is_ready,
                "analysis_type": analysis_type,
                "quality_score": quality_metrics.get("overall_quality", 0.0),
                "completeness": quality_metrics.get("completeness", 0.0),
                "recommendation": quality_metrics.get(
                    "analysis_recommendation", "insufficient"
                ),
            }

            # Add specific guidance
            if not is_ready:
                result["guidance"] = self._get_readiness_guidance(
                    analysis_type, quality_metrics
                )

            return result

        except Exception as e:
            logger.error(f"Error checking analysis readiness for user {user_id}: {e}")
            return {"is_ready": False, "analysis_type": analysis_type, "error": str(e)}

    def get_user_summary(self, user_id: int, period_days: int = 7) -> Dict[str, Any]:
        """
        Get high-level user summary for quick AI analysis
        """
        try:
            dataset = self.get_ai_ready_dataset(user_id, period_days, use_cache=True)
            processing_metadata = dataset.get("processing_metadata", {})

            # Extract key metrics for summary
            mood_data = dataset.get("mood_analytics", {})
            journal_data = dataset.get("journal_analytics", {})
            quality_metrics = dataset.get("quality_metrics", {})

            summary = {
                "user_id": user_id,
                "period_days": period_days,
                "collection_timestamp": processing_metadata.get("collection_timestamp"),
                "data_quality": quality_metrics.get("overall_quality", 0.0),
                "analysis_readiness": quality_metrics.get(
                    "analysis_recommendation", "unknown"
                ),
                "mood_summary": {
                    "entries_count": mood_data.get("total_entries", 0),
                    "average_mood": mood_data.get("average_mood", 0),
                    "trend": mood_data.get("trend_analysis", {}).get(
                        "trend", "unknown"
                    ),
                },
                "journal_summary": {
                    "entries_count": journal_data.get("total_entries", 0),
                    "total_words": journal_data.get("total_words", 0),
                    "writing_consistency": journal_data.get(
                        "writing_consistency", {}
                    ).get("score", 0),
                },
                "available_domains": [],
            }

            # Identify available data domains
            readiness_flags = quality_metrics.get("readiness_flags", {})
            for flag, is_ready in readiness_flags.items():
                if is_ready:
                    domain = flag.replace("ready_for_", "").replace("_analysis", "")
                    summary["available_domains"].append(domain)

            return summary

        except Exception as e:
            logger.error(f"Error getting user summary for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "period_days": period_days,
                "error": str(e),
                "data_quality": 0.0,
            }

    def invalidate_cache(self, user_id: int) -> bool:
        """
        Invalidate cached datasets for user (useful after new data is added)
        """
        try:
            from datawarehouse.models import AIAnalysisDataset

            # Mark existing datasets as inactive
            AIAnalysisDataset.objects.filter(user_id=user_id, is_active=True).update(
                is_active=False
            )

            logger.info(f"Invalidated cache for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error invalidating cache for user {user_id}: {e}")
            return False

    def _validate_dataset_quality(self, dataset: Dict[str, Any]) -> bool:
        """
        Validate the quality of retrieved dataset
        """
        try:
            quality_metrics = dataset.get("quality_metrics", {})
            overall_quality = quality_metrics.get("overall_quality", 0.0)
            completeness = quality_metrics.get("completeness", 0.0)

            # Basic quality thresholds
            return overall_quality >= 0.1 and completeness >= 0.1

        except Exception:
            return False

    def _get_readiness_guidance(
        self, analysis_type: str, quality_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Provide guidance on improving data readiness for specific analysis
        """
        domain_scores = quality_metrics.get("domain_scores", {})

        guidance = {
            "current_score": domain_scores.get(f"{analysis_type}_analytics", 0.0),
            "required_score": 0.3,
            "recommendations": [],
        }

        # Type-specific guidance
        if analysis_type == "mood":
            guidance["recommendations"] = [
                "Add more mood log entries over time",
                "Include activities and notes in mood logs",
                "Log mood consistently for better patterns",
            ]
        elif analysis_type == "journal":
            guidance["recommendations"] = [
                "Write more detailed journal entries",
                "Journal more consistently over time",
                "Include emotions and activities in entries",
            ]
        elif analysis_type == "behavior":
            guidance["recommendations"] = [
                "Log more app usage and activities",
                "Complete therapeutic exercises",
                "Engage with social features",
            ]
        else:
            guidance["recommendations"] = [
                f"Increase {analysis_type} data collection",
                "Use relevant app features more frequently",
                "Maintain consistent data entry patterns",
            ]

        return guidance

    def _create_empty_dataset(self, user_id: int, period_days: int) -> Dict[str, Any]:
        """
        Create empty dataset structure for error cases
        """
        return {
            "mood_analytics": {"status": "no_service", "entries_count": 0},
            "journal_analytics": {"status": "no_service", "entries_count": 0},
            "communication_analytics": {"status": "no_service"},
            "therapy_session_analytics": {"status": "no_service"},
            "behavioral_analytics": {"status": "no_service"},
            "social_analytics": {"status": "no_service"},
            "processed_insights": {"status": "no_service"},
            "quality_metrics": {
                "overall_quality": 0.0,
                "completeness": 0.0,
                "analysis_recommendation": "service_unavailable",
            },
            "processing_metadata": {
                "user_id": user_id,
                "period_days": period_days,
                "error": "datawarehouse_service_unavailable",
                "collection_timestamp": timezone.now().isoformat(),
            },
        }


# Create singleton instance
ai_data_interface = AIDataInterfaceService()

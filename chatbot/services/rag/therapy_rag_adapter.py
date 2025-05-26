from typing import Dict, Any, List
import logging
from .local_vector_store import local_vector_store
from .fallback_classifier import fallback_classifier

logger = logging.getLogger(__name__)


class TherapyRAGAdapter:
    """Adapter that uses local vector store for therapy recommendations"""

    def __init__(self):
        self.vector_store = local_vector_store
        self.fallback = fallback_classifier

    def get_therapy_approach(
        self, query: str, user_data: Dict = None
    ) -> Dict[str, Any]:
        """Get therapy approach recommendation using local vector store"""
        try:
            if not self.vector_store.loaded:
                logger.warning("Local vector store not loaded, using fallback")
                return self.fallback.classify_therapy_need(query)

            # Use local vector store to determine therapy approach
            therapy_type, confidence, supporting_chunks = (
                self.vector_store.determine_therapy_approach(query)
            )

            # Get relevant techniques based on the determined approach
            techniques = self._get_techniques_for_approach(
                therapy_type, supporting_chunks
            )

            # Get therapy info
            therapy_info = self._get_therapy_info(therapy_type)

            # Determine alternative approach
            alternative = "dbt" if therapy_type == "cbt" else "cbt"

            result = {
                "recommended_approach": therapy_type,
                "approach": therapy_type,  # For compatibility
                "confidence": confidence,
                "therapy_info": therapy_info,
                "recommended_techniques": techniques,
                "supporting_evidence": [
                    chunk.get("text", "")[:200] + "..."
                    for chunk in supporting_chunks[:3]
                ],
                "alternative_approach": alternative,
                "supporting_chunks": supporting_chunks,
            }

            logger.info(
                f"RAG recommendation: {therapy_type} (confidence: {confidence:.2f})"
            )
            return result

        except Exception as e:
            logger.error(f"Error in therapy approach recommendation: {str(e)}")
            return self.fallback.classify_therapy_need(query)

    def _get_techniques_for_approach(
        self, therapy_type: str, chunks: List[Dict]
    ) -> List[Dict]:
        """Extract techniques from supporting chunks"""
        techniques = []

        # Common CBT techniques
        cbt_techniques = [
            {
                "name": "Cognitive Restructuring",
                "description": "Identify and challenge negative thought patterns",
            },
            {
                "name": "Behavioral Activation",
                "description": "Increase engagement in meaningful activities",
            },
            {
                "name": "Thought Records",
                "description": "Track and analyze thoughts and emotions",
            },
            {
                "name": "Problem Solving",
                "description": "Systematic approach to addressing challenges",
            },
        ]

        # Common DBT techniques
        dbt_techniques = [
            {
                "name": "Mindfulness",
                "description": "Present-moment awareness and acceptance",
            },
            {
                "name": "Distress Tolerance",
                "description": "Skills to cope with crisis situations",
            },
            {
                "name": "Emotion Regulation",
                "description": "Understanding and managing emotions",
            },
            {
                "name": "Interpersonal Effectiveness",
                "description": "Skills for healthy relationships",
            },
        ]

        if therapy_type == "cbt":
            techniques = cbt_techniques[:2]  # Return top 2
        elif therapy_type == "dbt":
            techniques = dbt_techniques[:2]  # Return top 2
        else:
            # For unknown, provide general techniques
            techniques = [
                {
                    "name": "Mindful Breathing",
                    "description": "Simple breathing exercises for relaxation",
                },
                {
                    "name": "Journaling",
                    "description": "Write down thoughts and feelings",
                },
            ]

        return techniques

    def _get_therapy_info(self, therapy_type: str) -> Dict[str, Any]:
        """Get information about the therapy approach"""
        therapy_info = {
            "cbt": {
                "name": "Cognitive Behavioral Therapy",
                "description": "CBT focuses on identifying and changing negative thought patterns and behaviors.",
                "core_principles": [
                    "Thoughts, feelings, and behaviors are interconnected",
                    "Changing thoughts can change feelings and behaviors",
                    "Focus on present problems and solutions",
                ],
            },
            "dbt": {
                "name": "Dialectical Behavior Therapy",
                "description": "DBT combines acceptance and change strategies to help regulate emotions and improve relationships.",
                "core_principles": [
                    "Balance acceptance and change",
                    "Mindfulness and distress tolerance",
                    "Emotion regulation and interpersonal effectiveness",
                ],
            },
            "unknown": {
                "name": "General Therapeutic Approach",
                "description": "A personalized approach combining various therapeutic methods.",
                "core_principles": [
                    "Individual needs assessment",
                    "Flexible treatment approach",
                    "Focus on client strengths",
                ],
            },
        }

        return therapy_info.get(therapy_type, therapy_info["unknown"])

    def search_similar_content(
        self, query: str, therapy_type: str = None, limit: int = 5
    ) -> List[Dict]:
        """Search for similar content in the vector store"""
        try:
            if not self.vector_store.loaded:
                return []

            return self.vector_store.search_similar_chunks(query, therapy_type, limit)
        except Exception as e:
            logger.error(f"Error searching similar content: {str(e)}")
            return []


# Create singleton instance
therapy_rag_adapter = TherapyRAGAdapter()

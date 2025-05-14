#chatbot/services/rag/therapy_rag_service.py
import logging
import os
from typing import Dict, Any, List
from django.conf import settings
import json
from tqdm import tqdm  # newly added

from .pdf_extractor import pdf_extractor
from .vector_store import vector_store

logger = logging.getLogger(__name__)


class TherapyRAGService:
    """Service for therapy-specific RAG implementation."""

    def __init__(self):
        """Initialize the therapy RAG service."""
        self.data_dir = os.path.join(settings.BASE_DIR, "chatbot", "data")
        self.cbt_pdf_path = os.path.join(
            self.data_dir,
            "Cognitive therapy _ basics and beyond -- Judith S. Beck Phd -- ( WeLib.org ).pdf",
        )
        self.dbt_pdf_path = os.path.join(
            self.data_dir,
            "The Dialectical Behavior Therapy Skills Workbook ( PDFDrive ).pdf",
        )
        self.cbt_metadata = {
            "title": "Cognitive Therapy: Basics and Beyond",
            "author": "Judith S. Beck",
            "therapy_type": "Cognitive Behavioral Therapy",
            "description": "A foundational text on cognitive therapy principles and techniques",
        }
        self.dbt_metadata = {
            "title": "The Dialectical Behavior Therapy Skills Workbook",
            "therapy_type": "Dialectical Behavior Therapy",
            "description": "A practical workbook for DBT skills and techniques",
        }

    def setup_and_index_documents(self) -> Dict[str, Any]:
        """Extract content from PDFs, process them, and add to vector store.

        Returns:
            Dictionary with indexing results
        """
        results = {"cbt": {}, "dbt": {}}

        try:
            progress_bar = tqdm(total=6, desc="Indexing therapy documents", ncols=100)

            # Process CBT document
            logger.info("Processing CBT document...")
            cbt_text, cbt_chunks = pdf_extractor.extract_and_process(self.cbt_pdf_path)
            progress_bar.update(1)

            # Add to vector store
            cbt_doc_id = vector_store.add_document(
                "cbt", self.cbt_metadata["title"], self.cbt_pdf_path, self.cbt_metadata
            )
            progress_bar.update(1)
            cbt_chunks_added = vector_store.add_chunks(cbt_doc_id, cbt_chunks)
            progress_bar.update(1)

            results["cbt"] = {
                "document_id": cbt_doc_id,
                "chunks_added": cbt_chunks_added,
                "text_length": len(cbt_text),
            }

            # Process DBT document
            logger.info("Processing DBT document...")
            dbt_text, dbt_chunks = pdf_extractor.extract_and_process(self.dbt_pdf_path)
            progress_bar.update(1)

            # Add to vector store
            dbt_doc_id = vector_store.add_document(
                "dbt", self.dbt_metadata["title"], self.dbt_pdf_path, self.dbt_metadata
            )
            progress_bar.update(1)
            dbt_chunks_added = vector_store.add_chunks(dbt_doc_id, dbt_chunks)
            progress_bar.update(1)

            results["dbt"] = {
                "document_id": dbt_doc_id,
                "chunks_added": dbt_chunks_added,
                "text_length": len(dbt_text),
            }

            progress_bar.close()
            logger.info(
                f"Successfully indexed therapy documents: {json.dumps(results)}"
            )
            return results

        except Exception as e:
            logger.error(f"Error setting up therapy documents: {str(e)}")
            raise

    def get_therapy_approach(
        self, query: str, user_data: Dict = None
    ) -> Dict[str, Any]:
        """Determine which therapy approach is most appropriate for the user's query.

        Args:
            query: User's query or description of their situation
            user_data: Additional user context data

        Returns:
            Dictionary with recommended approach and supporting information
        """
        try:
            # Enhance query with user data if available
            enhanced_query = self._enhance_query_with_user_data(query, user_data)

            # Get therapy recommendation
            therapy_type, confidence, supporting_chunks = (
                vector_store.determine_therapy_approach(enhanced_query)
            )

            # Get therapy descriptions based on recommendation
            therapy_info = self._get_therapy_description(therapy_type)

            # Extract relevant techniques from supporting chunks
            techniques = self._extract_techniques_from_chunks(supporting_chunks)

            return {
                "query": query,
                "recommended_approach": therapy_type,
                "confidence": confidence,
                "therapy_info": therapy_info,
                "supporting_evidence": [
                    chunk["text"][:300] + "..." for chunk in supporting_chunks[:2]
                ],
                "recommended_techniques": techniques,
                "alternative_approach": "dbt" if therapy_type == "cbt" else "cbt",
            }

        except Exception as e:
            logger.error(f"Error getting therapy approach: {str(e)}")
            return {
                "error": str(e),
                "recommended_approach": "unknown",
                "confidence": 0.0,
            }

    def get_therapy_content(
        self, query: str, therapy_type: str = None, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get relevant therapy content for a specific query.

        Args:
            query: User's query or situation
            therapy_type: Optional filter for therapy type ('cbt' or 'dbt')
            limit: Maximum number of chunks to return

        Returns:
            List of relevant content chunks
        """
        try:
            return vector_store.search_similar_chunks(
                query, therapy_type=therapy_type, limit=limit
            )
        except Exception as e:
            logger.error(f"Error getting therapy content: {str(e)}")
            return []

    def _enhance_query_with_user_data(self, query: str, user_data: Dict = None) -> str:
        """Enhance the query with relevant user data for better matching.

        Args:
            query: Original query
            user_data: User context data

        Returns:
            Enhanced query string
        """
        if not user_data:
            return query

        enhanced_query = query

        # Add mood information if available
        if user_data.get("mood_logs") and len(user_data["mood_logs"]) > 0:
            recent_mood = user_data["mood_logs"][0]
            enhanced_query += f" The patient's recent mood rating is {recent_mood.get('mood_rating', 'unknown')}."

        # Add information from journal entries
        if user_data.get("journal_entries") and len(user_data["journal_entries"]) > 0:
            recent_entry = user_data["journal_entries"][0]
            content_snippet = (
                recent_entry.get("content", "")[:200]
                if recent_entry.get("content")
                else ""
            )
            if content_snippet:
                enhanced_query += f" From their journal: {content_snippet}"

        # Add analysis data
        if user_data.get("analysis"):
            analysis = user_data["analysis"]

            # Add emotional state
            if analysis.get("dominant_emotions"):
                emotions = ", ".join(analysis["dominant_emotions"][:2])
                enhanced_query += f" Their dominant emotions are {emotions}."

            # Add concerns
            if analysis.get("topics_of_concern"):
                concerns = ", ".join(analysis["topics_of_concern"][:2])
                enhanced_query += f" Their main concerns involve {concerns}."

            # Add communication patterns
            if analysis.get("communication_patterns", {}).get("communication_style"):
                enhanced_query += f" Their communication style is {analysis['communication_patterns']['communication_style']}."

        return enhanced_query

    def _get_therapy_description(self, therapy_type: str) -> Dict[str, str]:
        """Get descriptions and principles for the specified therapy type.

        Args:
            therapy_type: 'cbt' or 'dbt'

        Returns:
            Dictionary with therapy information
        """
        if therapy_type == "cbt":
            return {
                "name": "Cognitive Behavioral Therapy (CBT)",
                "description": "CBT focuses on identifying and changing negative thought patterns and behaviors. It helps patients understand the connections between thoughts, feelings, and behaviors.",
                "core_principles": [
                    "Thoughts influence emotions and behaviors",
                    "Identifying and challenging cognitive distortions",
                    "Problem-solving and developing coping skills",
                    "Setting goals and practicing new behaviors",
                    "Focus on present issues rather than past experiences",
                ],
                "best_for": [
                    "Depression",
                    "Anxiety disorders",
                    "Phobias",
                    "PTSD",
                    "OCD",
                    "Insomnia",
                    "Substance abuse",
                ],
            }
        elif therapy_type == "dbt":
            return {
                "name": "Dialectical Behavior Therapy (DBT)",
                "description": "DBT combines cognitive-behavioral techniques with mindfulness concepts, focusing on emotional regulation and distress tolerance. It balances acceptance and change strategies.",
                "core_principles": [
                    "Mindfulness - being present in the moment",
                    "Distress tolerance - coping with crisis without making it worse",
                    "Emotion regulation - understanding and managing emotions",
                    "Interpersonal effectiveness - maintaining relationships while respecting self",
                    "Balance between acceptance and change",
                ],
                "best_for": [
                    "Borderline personality disorder",
                    "Self-harm behaviors",
                    "Suicidal thoughts",
                    "Emotional dysregulation",
                    "Intense mood swings",
                    "Impulsive behaviors",
                    "Interpersonal conflicts",
                ],
            }
        else:
            return {
                "name": "General Therapeutic Approach",
                "description": "A personalized therapeutic approach combining various methods to address individual needs.",
                "core_principles": [
                    "Client-centered care",
                    "Evidence-based techniques",
                    "Personalization of treatment",
                    "Regular assessment of progress",
                    "Focus on wellness and growth",
                ],
                "best_for": [
                    "Various mental health concerns",
                    "Personal growth",
                    "Life transitions",
                    "Stress management",
                    "Overall wellbeing",
                ],
            }

    def _extract_techniques_from_chunks(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Extract therapeutic techniques from retrieved chunks.

        Args:
            chunks: List of text chunks

        Returns:
            List of techniques with descriptions
        """
        techniques = []

        # Extract potential techniques from chunks
        for chunk in chunks:
            text = chunk["text"]
            therapy_type = chunk.get("therapy_type", "unknown")

            # Simple extraction based on paragraph structure and keywords
            paragraphs = text.split("\n\n")
            for paragraph in paragraphs:
                if len(paragraph.strip()) < 30:  # Too short, likely not a technique
                    continue

                # Look for technique indicators
                technique_indicators = [
                    "technique",
                    "exercise",
                    "practice",
                    "skill",
                    "strategy",
                    "worksheet",
                    "method",
                    "approach",
                    "tool",
                    "activity",
                ]

                contains_indicator = any(
                    indicator in paragraph.lower() for indicator in technique_indicators
                )
                if contains_indicator:
                    # Extract the first sentence as the name
                    sentences = paragraph.split(".")
                    if not sentences:
                        continue

                    name = sentences[0].strip()
                    if len(name) > 100:  # Too long for a name
                        name = name[:100] + "..."

                    description = paragraph.strip()
                    if len(description) > 300:  # Truncate long descriptions
                        description = description[:300] + "..."

                    techniques.append(
                        {
                            "name": name,
                            "description": description,
                            "therapy_type": therapy_type,
                        }
                    )

                    # Limit to a reasonable number of techniques
                    if len(techniques) >= 5:
                        break

        # If no techniques found through this method, create generic ones based on therapy type
        if not techniques:
            therapy_type = chunks[0]["therapy_type"] if chunks else "unknown"
            if therapy_type == "cbt":
                techniques.append(
                    {
                        "name": "Thought Record",
                        "description": "Record and analyze negative thoughts, identify cognitive distortions, and develop more balanced alternatives.",
                        "therapy_type": "cbt",
                    }
                )
                techniques.append(
                    {
                        "name": "Behavioral Activation",
                        "description": "Schedule and engage in positive activities to improve mood and break cycles of avoidance.",
                        "therapy_type": "cbt",
                    }
                )
            elif therapy_type == "dbt":
                techniques.append(
                    {
                        "name": "Mindfulness Practice",
                        "description": "Focus attention on the present moment without judgment to improve emotional awareness.",
                        "therapy_type": "dbt",
                    }
                )
                techniques.append(
                    {
                        "name": "TIPP Skills for Distress Tolerance",
                        "description": "Temperature change, Intense exercise, Paced breathing, and Progressive muscle relaxation to manage overwhelming emotions.",
                        "therapy_type": "dbt",
                    }
                )

        return techniques


# Create instance for easy import
therapy_rag_service = TherapyRAGService()

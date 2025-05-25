from typing import List, Dict, Any, Tuple
from django.conf import settings
from django.db import connection
import logging
import numpy as np
import requests
import os

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for therapy documents using PostgreSQL with pgvector"""

    def __init__(self):
        self.embedding_model = getattr(settings, 'RAG_SETTINGS', {}).get('EMBEDDING_MODEL', 'nomic-embed-text:latest')
        self.embedding_dimension = getattr(settings, 'RAG_SETTINGS', {}).get('EMBEDDING_DIMENSION', 768)
        self.similarity_threshold = getattr(settings, 'RAG_SETTINGS', {}).get('SIMILARITY_THRESHOLD', 0.65)
        self.ollama_host = getattr(settings, 'RAG_SETTINGS', {}).get('OLLAMA_HOST', 'http://localhost:11434')

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text,
                    "options": {
                        "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", 50)),
                    },
                },
                timeout=30,
            )

            if response.status_code == 200:
                embedding = response.json().get("embedding")
                if embedding is None:
                    logger.error("No embedding found in response")
                    return [0.0] * self.embedding_dimension
                return embedding
            else:
                logger.error(f"Error generating embedding: {response.status_code}")
                return [0.0] * self.embedding_dimension

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return [0.0] * self.embedding_dimension

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        array1 = np.array(vec1)
        array2 = np.array(vec2)
        
        dot_product = np.dot(array1, array2)
        norm1 = np.linalg.norm(array1)
        norm2 = np.linalg.norm(array2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)

    def determine_therapy_approach(self, query: str) -> Tuple[str, float, List[Dict]]:
        """Determine the appropriate therapy approach based on query.
        
        Args:
            query: The user's query
            
        Returns:
            Tuple of (therapy_type, confidence, supporting_chunks)
        """
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            
            # Search both therapy types
            cbt_results = self._search_therapy_chunks("cbt", query_embedding)
            dbt_results = self._search_therapy_chunks("dbt", query_embedding)
            
            # Combine and sort results
            all_results = cbt_results + dbt_results
            all_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Get top results
            top_results = all_results[:10]
            
            if not top_results:
                return "unknown", 0.2, []
            
            # Count therapy types in top results
            cbt_count = sum(1 for r in top_results if r["therapy_type"] == "cbt")
            dbt_count = sum(1 for r in top_results if r["therapy_type"] == "dbt")
            
            # Calculate average similarity for each therapy type
            cbt_similarity = sum(r["similarity"] for r in top_results if r["therapy_type"] == "cbt")
            dbt_similarity = sum(r["similarity"] for r in top_results if r["therapy_type"] == "dbt")
            
            if cbt_count > 0:
                cbt_similarity /= cbt_count
            if dbt_count > 0:
                dbt_similarity /= dbt_count
            
            # Determine therapy type based on count and similarity
            if cbt_count > dbt_count:
                therapy_type = "cbt"
                confidence = min(0.95, max(0.5, cbt_similarity))
            elif dbt_count > cbt_count:
                therapy_type = "dbt"
                confidence = min(0.95, max(0.5, dbt_similarity))
            else:
                # Equal counts, use highest similarity
                if cbt_similarity > dbt_similarity:
                    therapy_type = "cbt"
                    confidence = min(0.95, max(0.5, cbt_similarity))
                else:
                    therapy_type = "dbt"
                    confidence = min(0.95, max(0.5, dbt_similarity))
            
            # If confidence is too low, return unknown
            if confidence < self.similarity_threshold:
                return "unknown", 0.2, top_results
                
            return therapy_type, confidence, top_results
            
        except Exception as e:
            logger.error(f"Error determining therapy approach: {str(e)}")
            return "unknown", 0.2, []

    def _search_therapy_chunks(self, therapy_type: str, query_embedding: List[float]) -> List[Dict]:
        """Search chunks of a specific therapy type using database"""
        try:
            with connection.cursor() as cursor:
                # Convert embedding to string format for PostgreSQL
                embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                
                cursor.execute("""
                    SELECT tc.id, tc.text, tc.metadata, td.therapy_type,
                           1 - (tc.embedding <=> %s::vector) as similarity
                    FROM therapy_chunks tc
                    JOIN therapy_documents td ON tc.document_id = td.id
                    WHERE td.therapy_type = %s
                      AND 1 - (tc.embedding <=> %s::vector) > %s
                    ORDER BY tc.embedding <=> %s::vector
                    LIMIT 20
                """, [embedding_str, therapy_type, embedding_str, self.similarity_threshold, embedding_str])
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "text": row[1],
                        "metadata": row[2] or {},
                        "therapy_type": row[3],
                        "similarity": float(row[4])
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error searching {therapy_type} chunks: {str(e)}")
            return []

    def search_similar_chunks(self, query: str, therapy_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query
        
        Args:
            query: The search query
            therapy_type: Optional therapy type to filter results
            limit: Maximum number of results to return
            
        Returns:
            List of similar chunks
        """
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            
            # Search in specified therapy type or both
            if therapy_type and therapy_type in ["cbt", "dbt"]:
                results = self._search_therapy_chunks(therapy_type, query_embedding)
            else:
                cbt_results = self._search_therapy_chunks("cbt", query_embedding)
                dbt_results = self._search_therapy_chunks("dbt", query_embedding)
                results = cbt_results + dbt_results
                results.sort(key=lambda x: x["similarity"], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            return []


# Create instance for easy import
vector_store = VectorStore()

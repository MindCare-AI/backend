# chatbot/services/rag/local_vector_store.py
import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Tuple
from django.conf import settings
import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)


class LocalVectorStore:
    """Local file-based vector store for document embeddings."""

    def __init__(self):
        """Initialize the local vector store with GPU acceleration."""
        self.chunks_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "chunks")
        self.cbt_dir = os.path.join(self.chunks_dir, "cbt")
        self.dbt_dir = os.path.join(self.chunks_dir, "dbt")
        self.index_dir = os.path.join(self.chunks_dir, "index")

        # Configure GPU acceleration
        self._setup_gpu_acceleration()

        # Load configuration and indexes
        self.loaded = self._load_store()
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
        self.embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", 768))
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", 0.65))
        self.cache_enabled = True
        self.cache = {}

    def _setup_gpu_acceleration(self):
        """Set up GPU acceleration for embeddings."""
        try:
            # Use max GPU layers by default
            if not os.getenv("OLLAMA_NUM_GPU"):
                os.environ["OLLAMA_NUM_GPU"] = "80"  # Maximum GPU usage
                logger.info("Set OLLAMA_NUM_GPU=80 for maximum GPU acceleration")

            # Try to import and check for GPU availability
            try:
                from chatbot.services.rag.gpu_utils import verify_gpu_support

                gpu_info = verify_gpu_support()
                if (
                    gpu_info
                    and isinstance(gpu_info, dict)
                    and gpu_info.get("using_gpu")
                ):
                    logger.info(
                        f"GPU acceleration enabled: {gpu_info.get('details', '')}"
                    )
                else:
                    logger.warning("GPU not detected or not configured properly")
            except ImportError:
                logger.warning("Could not import gpu_utils, skipping GPU verification")
        except Exception as e:
            logger.warning(f"Error setting up GPU acceleration: {e}")

    def _load_store(self) -> bool:
        """Load the local vector store configuration and indexes."""
        try:
            if not os.path.exists(self.chunks_dir):
                logger.error(f"Chunks directory not found: {self.chunks_dir}")
                return False

            # Load config
            config_path = os.path.join(self.chunks_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    self.config = json.load(f)
            else:
                logger.warning(f"Config file not found: {config_path}")
                self.config = {}

            # Load document index
            doc_index_path = os.path.join(self.index_dir, "documents.json")
            if os.path.exists(doc_index_path):
                with open(doc_index_path, "r") as f:
                    self.documents = json.load(f)
            else:
                logger.warning(f"Document index not found: {doc_index_path}")
                self.documents = {}

            # Load chunk indexes
            cbt_index_path = os.path.join(self.index_dir, "cbt_chunks.json")
            if os.path.exists(cbt_index_path):
                with open(cbt_index_path, "r") as f:
                    self.cbt_chunks = json.load(f)
            else:
                logger.warning(f"CBT chunk index not found: {cbt_index_path}")
                self.cbt_chunks = []

            dbt_index_path = os.path.join(self.index_dir, "dbt_chunks.json")
            if os.path.exists(dbt_index_path):
                with open(dbt_index_path, "r") as f:
                    self.dbt_chunks = json.load(f)
            else:
                logger.warning(f"DBT chunk index not found: {dbt_index_path}")
                self.dbt_chunks = []

            logger.info(
                f"Local vector store loaded with {len(self.documents)} documents, "
                + f"{len(self.cbt_chunks)} CBT chunks, {len(self.dbt_chunks)} DBT chunks"
            )

            return True

        except Exception as e:
            logger.error(f"Error loading local vector store: {str(e)}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text with caching for frequently used queries."""
        # Check cache first if enabled
        if self.cache_enabled:
            cache_key = hash(text)
            if cache_key in self.cache:
                return self.cache[cache_key]

        # Clean text before embedding
        clean_text = self._clean_text_for_embedding(text)

        try:
            # Set GPU layers for Ollama if not set
            gpu_layers_env = os.getenv("OLLAMA_NUM_GPU")
            if not gpu_layers_env:
                os.environ["OLLAMA_NUM_GPU"] = "80"  # Maximum GPU usage
                logger.info("Set OLLAMA_NUM_GPU=80 for maximum GPU acceleration")

            # Make request to Ollama API with GPU acceleration
            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": clean_text,
                    "options": {
                        "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", 80)),
                        "use_gpu": True,
                    },
                },
                timeout=30,  # Add timeout to prevent hanging requests
            )

            if response.status_code == 200:
                embedding = response.json().get("embedding")
                if embedding is None:
                    logger.error("No embedding found in response")
                    embedding = [0.0] * self.embedding_dimension

                # Store in cache if enabled
                if self.cache_enabled:
                    self.cache[cache_key] = embedding

                return embedding
            else:
                logger.error(
                    f"Error generating embedding: {response.status_code}, {response.text}"
                )
                return [0.0] * self.embedding_dimension

        except requests.exceptions.Timeout:
            logger.error("Timeout when generating embedding")
            raise
        except requests.exceptions.ConnectionError:
            logger.error("Connection error when generating embedding")
            raise
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return [0.0] * self.embedding_dimension

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch for GPU efficiency.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        results = []
        cache_hits = 0

        # First check cache for all texts
        to_embed = []
        cache_results = {}

        if self.cache_enabled:
            for i, text in enumerate(texts):
                cache_key = hash(text)
                if cache_key in self.cache:
                    cache_results[i] = self.cache[cache_key]
                    cache_hits += 1
                else:
                    to_embed.append((i, text))
        else:
            to_embed = [(i, text) for i, text in enumerate(texts)]

        # If all found in cache, return early
        if not to_embed:
            # Return embeddings in original order
            return [cache_results[i] for i in range(len(texts))]

        # Clean texts
        cleaned_texts = [self._clean_text_for_embedding(text) for _, text in to_embed]

        # Process batches of reasonable size to avoid exceeding GPU memory
        batch_size = 16
        all_embeddings = {}

        for i in range(0, len(cleaned_texts), batch_size):
            batch = cleaned_texts[i : i + batch_size]
            batch_indices = [
                to_embed[j][0] for j in range(i, min(i + batch_size, len(to_embed)))
            ]

            try:
                # Make request to Ollama API with batch
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": batch,
                        "options": {
                            "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", 80)),
                            "use_gpu": True,
                        },
                    },
                    timeout=60,  # Longer timeout for batches
                )

                if response.status_code == 200:
                    embeddings = response.json().get("embeddings", [])

                    # Store results and update cache
                    for idx, embedding in zip(batch_indices, embeddings):
                        all_embeddings[idx] = embedding

                        if self.cache_enabled:
                            original_idx, original_text = to_embed[idx - i]
                            self.cache[hash(original_text)] = embedding
                else:
                    logger.error(
                        f"Error in batch embedding: {response.status_code}, {response.text}"
                    )
                    # Fall back to single embeddings
                    for j, text in enumerate(batch):
                        idx = batch_indices[j]
                        all_embeddings[idx] = self.generate_embedding(
                            to_embed[idx - i][1]
                        )

            except Exception as e:
                logger.error(f"Error in batch embedding: {str(e)}")
                # Fall back to single embeddings
                for j, text in enumerate(batch):
                    if j < len(batch_indices):
                        idx = batch_indices[j]
                        all_embeddings[idx] = self.generate_embedding(
                            to_embed[idx - i][1]
                        )

        # Combine cache and new embeddings in original order
        results = []
        for i in range(len(texts)):
            if i in cache_results:
                results.append(cache_results[i])
            elif i in all_embeddings:
                results.append(all_embeddings[i])
            else:
                # Fallback - shouldn't happen but just in case
                results.append([0.0] * self.embedding_dimension)

        logger.info(
            f"Generated batch embeddings: {len(texts)} texts, {cache_hits} from cache, {len(results)} results"
        )

        return results

    def _clean_text_for_embedding(self, text: str) -> str:
        """Clean and prepare text for embedding to improve vector quality."""
        if not text:
            return ""

        # Remove excessive whitespace
        text = text.strip()

        # Truncate very long texts to avoid token limits
        max_chars = 8000  # Approximate character limit
        if len(text) > max_chars:
            text = text[:max_chars]

        return text

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        # Convert to numpy arrays for faster computation
        array1 = np.array(vec1)
        array2 = np.array(vec2)

        # Compute cosine similarity
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
        if not self.loaded:
            logger.error("Local vector store not loaded")
            return "unknown", 0.2, []

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
        cbt_similarity = sum(
            r["similarity"] for r in top_results if r["therapy_type"] == "cbt"
        )
        dbt_similarity = sum(
            r["similarity"] for r in top_results if r["therapy_type"] == "dbt"
        )

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

    def _search_therapy_chunks(
        self, therapy_type: str, query_embedding: List[float]
    ) -> List[Dict]:
        """Search chunks of a specific therapy type."""
        results = []

        # Get chunk IDs for this therapy type
        chunk_ids = self.cbt_chunks if therapy_type == "cbt" else self.dbt_chunks

        # Load each chunk and calculate similarity
        for chunk_id in chunk_ids:
            chunk_path = os.path.join(self.chunks_dir, therapy_type, f"{chunk_id}.json")

            if not os.path.exists(chunk_path):
                continue

            try:
                with open(chunk_path, "r") as f:
                    chunk_data = json.load(f)

                chunk_embedding = chunk_data.get("embedding")

                if not chunk_embedding:
                    continue

                similarity = self.cosine_similarity(query_embedding, chunk_embedding)

                if similarity > self.similarity_threshold:
                    results.append(
                        {
                            "id": chunk_data.get("id"),
                            "document_id": chunk_data.get("document_id"),
                            "text": chunk_data.get("text"),
                            "similarity": similarity,
                            "therapy_type": therapy_type,
                        }
                    )
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_id}: {str(e)}")

        # Sort results by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results[:20]  # Return top 20 chunks

    def search_similar_chunks(
        self, query: str, therapy_type: str = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query.

        Args:
            query: The search query
            therapy_type: Optional therapy type to filter results
            limit: Maximum number of results to return

        Returns:
            List of similar chunks
        """
        if not self.loaded:
            logger.error("Local vector store not loaded")
            return []

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


# Create instance for easy import
local_vector_store = LocalVectorStore()

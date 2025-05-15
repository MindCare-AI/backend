# chatbot/services/rag/vector_store.py

import numpy as np
from psycopg2 import pool
import logging
import requests
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from psycopg2.extras import execute_values, Json
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_random_exponential
from contextlib import contextmanager  # Add this import

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for document embeddings using PostgreSQL with pgvector."""

    def __init__(self):
        """Initialize the vector store with database configuration."""
        self.db_config = {
            "dbname": settings.DATABASES["default"]["NAME"],
            "user": settings.DATABASES["default"]["USER"],
            "password": settings.DATABASES["default"]["PASSWORD"],
            "host": settings.DATABASES["default"]["HOST"],
            "port": settings.DATABASES["default"]["PORT"],
        }
        # Initialize a threaded connection pool
        min_conn = int(os.getenv("DB_POOL_MIN_CONN", 1))
        max_conn = int(os.getenv("DB_POOL_MAX_CONN", 5))
        self.pool = pool.ThreadedConnectionPool(min_conn, max_conn, **self.db_config)
        self.embed_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
        # Update embedding dimension to match nomic-embed-text's actual output dimension
        self.embedding_dimension = int(
            os.getenv("EMBEDDING_DIMENSION", 768)
        )  # Changed from 384 to 768
        self.gpu_layers = int(os.getenv("OLLAMA_NUM_GPU", 50))
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self._setup_vector_store()

    @contextmanager
    def _get_cursor(self):
        """Context‐manager: yield (conn, cursor), commit/rollback, and return connection to pool."""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            yield conn, cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self.pool.putconn(conn)

    def _setup_vector_store(self):
        """Set up the database with necessary tables and extensions."""
        try:
            # First, check if tables exist - if they do and have wrong dimension, drop them
            self._check_and_recreate_tables_if_needed()
            # Then set up the database with the correct dimensions
            self.setup_db()
            # Pull the embedding model to ensure it's available
            self._ensure_model_pulled()
        except Exception as e:
            logger.error(f"Error setting up vector store: {str(e)}")
            raise

    def _ensure_model_pulled(self):
        """Make sure the embedding model is pulled from Ollama."""
        try:
            import requests

            logger.info(
                f"Checking if embedding model {self.embed_model} is available..."
            )

            # Just check if the model exists by sending a small embedding request
            try:
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={"model": self.embed_model, "prompt": "Test"},
                    timeout=10,  # Short timeout just to check
                )
                if response.status_code == 200:
                    logger.info(f"Embedding model {self.embed_model} is ready")
                    return True
            except requests.exceptions.RequestException:
                logger.warning(
                    f"Embedding model {self.embed_model} not immediately available"
                )

            # If we got here, we need to pull the model
            logger.info(f"Pulling embedding model {self.embed_model}...")

            # Use subprocess to call the management command with timeout
            import subprocess
            import sys
            from django.conf import settings

            # Construct the command to run the pull_embedding_model command
            cmd = [
                sys.executable,
                os.path.join(settings.BASE_DIR, "manage.py"),
                "pull_embedding_model",
                "--timeout",
                "300",
            ]

            try:
                subprocess.run(cmd, check=True, timeout=310)
                logger.info(f"Embedding model {self.embed_model} is ready")
                return True
            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                logger.error(f"Could not pull embedding model: {str(e)}")
                raise Exception(f"Failed to pull embedding model: {str(e)}")

        except Exception as e:
            logger.warning(f"Could not verify embedding model: {str(e)}")
            return False

    def _check_and_recreate_tables_if_needed(self):
        """Check if tables exist with wrong dimension and recreate if needed."""
        try:
            with self._get_cursor() as (conn, cursor):
                # Check if the therapy_chunks table exists
                cursor.execute("""
                    SELECT EXISTS (
                       SELECT FROM information_schema.tables 
                       WHERE table_name = 'therapy_chunks'
                    );
                """)
                table_exists = cursor.fetchone()[0]

                if table_exists:
                    # Check the vector dimension of the embedding column
                    try:
                        cursor.execute("""
                            SELECT typelem FROM pg_type WHERE typname = 'vector';
                            SELECT atttypmod FROM pg_attribute 
                            WHERE attrelid = 'therapy_chunks'::regclass 
                            AND attname = 'embedding';
                        """)
                        # If the dimension doesn't match, drop the tables
                        cursor.execute("""
                            DROP TABLE IF EXISTS therapy_chunks;
                            DROP TABLE IF EXISTS therapy_documents;
                        """)
                        conn.commit()
                        logger.info(
                            "Dropped existing tables with incorrect embedding dimension"
                        )
                    except Exception:
                        # If error, it's safer to drop and recreate
                        cursor.execute("""
                            DROP TABLE IF EXISTS therapy_chunks;
                            DROP TABLE IF EXISTS therapy_documents;
                        """)
                        conn.commit()
                        logger.info(
                            "Dropped existing tables due to error checking dimension"
                        )
        except Exception as e:
            logger.error(f"Error checking tables: {str(e)}")
            raise

    def setup_db(self):
        """Set up the database with necessary extensions and tables."""
        try:
            with self._get_cursor() as (conn, cursor):
                # Enable pgvector extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

                # Create tables if they don't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS therapy_documents (
                        id SERIAL PRIMARY KEY,
                        therapy_type VARCHAR(50) NOT NULL,
                        document_name TEXT NOT NULL,
                        document_path TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                # Create therapy_chunks table with the updated embedding dimension
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS therapy_chunks (
                        id SERIAL PRIMARY KEY,
                        document_id INTEGER REFERENCES therapy_documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector({self.embedding_dimension}),
                        metadata JSONB DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(document_id, chunk_index)
                    )
                """)

                # Create index for faster similarity search
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS therapy_chunks_embedding_idx 
                    ON therapy_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """)

                logger.info(
                    f"Set up database with embedding dimension {self.embedding_dimension}"
                )
        except Exception as e:
            logger.error(f"Error setting up database: {str(e)}")
            raise

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text using Ollama API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as a numpy array
        """
        try:
            # Log GPU usage
            logger.info(f"Using GPU layers: {self.gpu_layers}")  # Log GPU layers

            # Truncate extremely long texts to avoid API failures
            if len(text) > 8000:
                logger.warning(
                    "Truncating text longer than 8000 characters for embedding"
                )
                text = text[:8000]

            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text,
                    "options": {"num_gpu": self.gpu_layers},  # Ensure GPU layers are passed
                },
                timeout=30,
            )
            response.raise_for_status()
            embedding = np.array(response.json()["embedding"])

            # Make sure embedding dimensions match our expected dimension
            if embedding.shape[0] != self.embedding_dimension:
                logger.warning(
                    f"Embedding dimension mismatch: got {embedding.shape[0]}, expected {self.embedding_dimension}"
                )
                # If dimensions are close, we can pad or truncate
                if embedding.shape[0] > self.embedding_dimension:
                    embedding = embedding[: self.embedding_dimension]
                elif embedding.shape[0] < self.embedding_dimension:
                    padding = np.zeros(self.embedding_dimension - embedding.shape[0])
                    embedding = np.concatenate([embedding, padding])

            return embedding
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            raise

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
    def _get_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts using Ollama API.
        Process each text individually as Ollama API doesn't support true batching.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors as numpy arrays
        """
        results = []

        for i, text in enumerate(texts):
            try:
                # Ensure text isn't too long - limit to 8000 chars to prevent errors
                if len(text) > 8000:
                    logger.warning(
                        f"Text at index {i} truncated from {len(text)} to 8000 characters"
                    )
                    text = text[:8000]

                # Process one text at a time
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={
                        "model": self.embed_model,
                        "prompt": text,  # Single text, not a batch
                        "options": {"num_gpu": self.gpu_layers},
                    },
                    timeout=30,  # Shorter timeout for individual requests
                )

                if response.status_code != 200:
                    logger.error(
                        f"Embedding error for text {i}: {response.status_code} {response.reason}"
                    )
                    # Log a small portion of the text for debugging
                    logger.error(f"Text preview: {text[:100]}...")
                    response.raise_for_status()

                # Extract embedding from response
                embedding = np.array(response.json()["embedding"])

                # Ensure embedding has correct dimension
                if embedding.shape[0] != self.embedding_dimension:
                    logger.warning(
                        f"Embedding dimension mismatch: got {embedding.shape[0]}, expected {self.embedding_dimension}"
                    )
                    if embedding.shape[0] > self.embedding_dimension:
                        embedding = embedding[: self.embedding_dimension]
                    elif embedding.shape[0] < self.embedding_dimension:
                        padding = np.zeros(
                            self.embedding_dimension - embedding.shape[0]
                        )
                        embedding = np.concatenate([embedding, padding])

                results.append(embedding)

            except Exception as e:
                logger.error(f"Error embedding text {i}: {str(e)}")
                # If we can't get a valid embedding, add a zero vector to maintain order
                results.append(np.zeros(self.embedding_dimension))

        return results

    def add_document(
        self,
        therapy_type: str,
        document_name: str,
        document_path: str,
        metadata: Dict = None,
    ) -> int:
        """Add a new document to the store.

        Args:
            therapy_type: Type of therapy ('cbt' or 'dbt')
            document_name: Name/title of the document
            document_path: Path to the document
            metadata: Additional metadata for the document

        Returns:
            ID of the inserted document
        """
        if metadata is None:
            metadata = {}

        try:
            with self._get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    INSERT INTO therapy_documents (therapy_type, document_name, document_path, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """,
                    (therapy_type.lower(), document_name, document_path, Json(metadata)),
                )

                document_id = cursor.fetchone()[0]
                return document_id

        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise

    def add_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> int:
        """Add text chunks with embeddings to the store with batch processing."""
        if not chunks:
            return 0

        # Better batch size based on GPU memory
        BATCH_SIZE = 10 if self.gpu_layers > 0 else 5
        total_added = 0

        # Add progress indication to console
        from tqdm import tqdm

        chunk_batches = list(range(0, len(chunks), BATCH_SIZE))

        with tqdm(
            total=len(chunk_batches),
            desc="Processing chunk batches",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ) as pbar:
            for i in chunk_batches:
                batch = chunks[i : i + BATCH_SIZE]
                batch_texts = [chunk["text"] for chunk in batch]

                try:
                    # Pre-process texts - truncate long texts before sending to API
                    for j, text in enumerate(batch_texts):
                        if len(text) > 8000:
                            logger.info(
                                f"Text at index {j} truncated from {len(text)} to 8000 characters"
                            )
                            batch_texts[j] = text[:8000]

                    embeddings = self._get_embeddings_batch(batch_texts)

                    values = []
                    for chunk_index, (chunk, embedding) in enumerate(
                        zip(batch, embeddings)
                    ):
                        values.append(
                            (
                                document_id,
                                i + chunk_index,  # Global chunk index
                                chunk["text"][
                                    :8000
                                ],  # Ensure text is truncated for database
                                embedding.tolist(),
                                json.dumps(chunk.get("metadata", {})),
                            )
                        )

                    with self._get_cursor() as (conn, cursor):
                        execute_values(
                            cursor,
                            """
                            INSERT INTO therapy_chunks 
                                (document_id, chunk_index, chunk_text, embedding, metadata)
                            VALUES %s
                            ON CONFLICT (document_id, chunk_index) 
                            DO UPDATE SET 
                                chunk_text = EXCLUDED.chunk_text,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata
                            """,
                            values,
                        )
                        total_added += len(batch)
                        pbar.update(1)

                except Exception as e:
                    logger.error(f"Error processing batch {i//BATCH_SIZE}: {str(e)}")
                    # Continue with next batch instead of failing completely
                    pbar.update(1)
                    continue

        return total_added

    def search_similar_chunks(
        self,
        query: str,
        therapy_type: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query with improved filtering.

        Args:
            query: Search query
            therapy_type: Optional filter for therapy type ('cbt', 'dbt', or None for both)
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of similar chunks with similarity scores
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)

            with self._get_cursor() as (conn, cursor):
                # Build query based on whether therapy_type is specified
                # Added minimum similarity threshold
                if therapy_type:
                    sql = """
                        SELECT tc.chunk_text, tc.metadata, td.therapy_type, 
                               1 - (tc.embedding <=> %s::vector) as similarity
                        FROM therapy_chunks tc
                        JOIN therapy_documents td ON tc.document_id = td.id
                        WHERE td.therapy_type = %s AND 1 - (tc.embedding <=> %s::vector) > %s
                        ORDER BY similarity DESC
                        LIMIT %s
                    """
                    cursor.execute(
                        sql,
                        (
                            query_embedding.tolist(),
                            therapy_type.lower(),
                            query_embedding.tolist(),
                            min_similarity,
                            limit,
                        ),
                    )
                else:
                    sql = """
                        SELECT tc.chunk_text, tc.metadata, td.therapy_type, 
                               1 - (tc.embedding <=> %s::vector) as similarity
                        FROM therapy_chunks tc
                        JOIN therapy_documents td ON tc.document_id = td.id
                        WHERE 1 - (tc.embedding <=> %s::vector) > %s
                        ORDER BY similarity DESC
                        LIMIT %s
                    """
                    cursor.execute(
                        sql,
                        (
                            query_embedding.tolist(),
                            query_embedding.tolist(),
                            min_similarity,
                            limit,
                        ),
                    )

                results = []
                for chunk_text, metadata, doc_therapy_type, similarity in cursor.fetchall():
                    results.append(
                        {
                            "text": chunk_text,
                            "therapy_type": doc_therapy_type,
                            "metadata": metadata,
                            "similarity": float(similarity),
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            raise

    def determine_therapy_approach(self, query: str) -> Tuple[str, float, List[Dict]]:
        """Determine which therapy approach (CBT or DBT) is more suitable for the query.

        Args:
            query: User query or description of symptoms/situation

        Returns:
            Tuple of (recommended_therapy_type, confidence_score, supporting_chunks)
        """
        try:
            # Get relevant chunks from both therapy types
            cbt_chunks = self.search_similar_chunks(query, therapy_type="cbt", limit=3)
            dbt_chunks = self.search_similar_chunks(query, therapy_type="dbt", limit=3)

            # Calculate average similarity scores
            cbt_avg_score = (
                sum(chunk["similarity"] for chunk in cbt_chunks) / len(cbt_chunks)
                if cbt_chunks
                else 0
            )
            dbt_avg_score = (
                sum(chunk["similarity"] for chunk in dbt_chunks) / len(dbt_chunks)
                if dbt_chunks
                else 0
            )

            # Determine which approach has higher relevance
            if cbt_avg_score > dbt_avg_score:
                recommended_therapy = "cbt"
                confidence = cbt_avg_score
                supporting_chunks = cbt_chunks
            else:
                recommended_therapy = "dbt"
                confidence = dbt_avg_score
                supporting_chunks = dbt_chunks

            return recommended_therapy, confidence, supporting_chunks

        except Exception as e:
            logger.error(f"Error determining therapy approach: {str(e)}")
            return "unknown", 0.0, []


# Create instance for easy import
vector_store = VectorStore()

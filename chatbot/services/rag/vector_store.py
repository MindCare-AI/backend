# chatbot/services/rag/vector_store.py

from psycopg2 import pool
import logging
import requests
import os
import re
from typing import List, Dict, Any, Tuple
from psycopg2.extras import execute_values, Json
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_random_exponential
from contextlib import contextmanager

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
        # enforce SSL for Neon cloud databases
        if "neon.tech" in self.db_config.get("host", ""):
            self.db_config["sslmode"] = "require"
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

        # Enhanced configuration for better accuracy
        self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", 0.65))
        self.similarity_quantile = float(os.getenv("SIMILARITY_QUANTILE", 0.75))
        # per-therapy overrides
        self.similarity_threshold_cbt = float(os.getenv("SIMILARITY_THRESHOLD_CBT", self.similarity_threshold))
        self.similarity_threshold_dbt = float(os.getenv("SIMILARITY_THRESHOLD_DBT", self.similarity_threshold))
        self.max_retrieval_count = int(os.getenv("MAX_RETRIEVAL_COUNT", 10))
        self.enable_reranking = os.getenv("ENABLE_RERANKING", "true").lower() == "true"
        self.enable_hybrid_search = os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true"
        self.keyword_weight = float(os.getenv("KEYWORD_WEIGHT", 0.25))
        self.semantic_weight = float(os.getenv("SEMANTIC_WEIGHT", 0.75))
        self.cache_enabled = os.getenv("ENABLE_EMBEDDING_CACHE", "true").lower() == "true"
        self.cache_size = int(os.getenv("EMBEDDING_CACHE_SIZE", 1000))
        self.embedding_cache = {}  # In-memory LRU cache for embeddings
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
        """Setup the vector store tables in PostgreSQL."""
        try:
            with self._get_cursor() as (conn, cursor):
                # Create extension if not exists
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create tables if they don't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS therapy_documents (
                        id SERIAL PRIMARY KEY,
                        therapy_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        file_path TEXT,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS therapy_chunks (
                        id SERIAL PRIMARY KEY,
                        document_id INTEGER REFERENCES therapy_documents(id) ON DELETE CASCADE,
                        text TEXT NOT NULL,
                        embedding vector(%s),
                        metadata JSONB,
                        sequence INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """ % self.embedding_dimension)
                
                # Create index for faster similarity search
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS therapy_chunks_embedding_idx 
                    ON therapy_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                logger.info("Vector store setup complete")
        except Exception as e:
            logger.error(f"Error setting up vector store: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text with caching for frequently used queries.

        Args:
            text: Text to embed

        Returns:
            List of embedding values
        """
        # Check cache first if enabled
        if self.cache_enabled:
            cache_key = hash(text)
            if cache_key in self.embedding_cache:
                return self.embedding_cache[cache_key]

        # Clean text before embedding
        clean_text = self._clean_text_for_embedding(text)

        try:
            # Make request to Ollama API
            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={"model": self.embed_model, "prompt": clean_text},
                timeout=30  # Add timeout to prevent hanging requests
            )

            if response.status_code == 200:
                embedding = response.json().get("embedding")
                if embedding is None:
                    logger.error("No embedding found in response")
                    embedding = [0.0] * self.embedding_dimension

                # Store in cache if enabled
                if self.cache_enabled:
                    self.embedding_cache[cache_key] = embedding

                return embedding
            else:
                logger.error(f"Error generating embedding: {response.status_code}, {response.text}")
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

    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding vector to unit length for better similarity comparisons."""
        if not embedding:
            return [0.0] * self.embedding_dimension

        # Calculate vector magnitude
        magnitude = sum(x * x for x in embedding) ** 0.5

        if magnitude > 0:
            # Normalize to unit vector
            return [x / magnitude for x in embedding]
        return embedding

    def _clean_text_for_embedding(self, text: str) -> str:
        """Clean and prepare text for embedding to improve vector quality."""
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Truncate very long texts to avoid token limits
        max_chars = 8000  # Approximate character limit
        if len(text) > max_chars:
            # Try to truncate at sentence boundary
            truncated = text[:max_chars]
            last_period = truncated.rfind('.')
            if last_period > max_chars * 0.8:  # Only truncate at sentence if it's not too short
                truncated = truncated[:last_period+1]
            text = truncated

        return text

    def add_document(self, therapy_type: str, title: str, file_path: str, metadata: Dict = None) -> int:
        """Add a document to the vector store.
        
        Args:
            therapy_type: Type of therapy ('cbt' or 'dbt')
            title: Document title
            file_path: Path to the document file
            metadata: Optional metadata dictionary
            
        Returns:
            Document ID
        """
        try:
            with self._get_cursor() as (conn, cursor):
                # Use Json adapter from psycopg2.extras for proper JSONB handling
                cursor.execute(
                    """
                    INSERT INTO therapy_documents (therapy_type, title, file_path, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (therapy_type, title, file_path, Json(metadata) if metadata else None)
                )
                document_id = cursor.fetchone()[0]
                return document_id
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise

    def add_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> int:
        """Add chunks to the vector store efficiently using execute_values.
        
        Args:
            document_id: ID of the document these chunks belong to
            chunks: List of chunk dictionaries with text and metadata
            
        Returns:
            Number of chunks added
        """
        try:
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                # Generate embedding for each chunk
                text = chunk.get("text", "")
                if not text:
                    continue
                    
                embedding = self.generate_embedding(text)
                processed_chunks.append((
                    document_id,
                    text,
                    embedding,
                    Json(chunk.get("metadata", {})),
                    i  # sequence number
                ))
            
            with self._get_cursor() as (conn, cursor):
                # Use execute_values for efficient bulk insertion
                execute_values(
                    cursor,
                    """
                    INSERT INTO therapy_chunks 
                    (document_id, text, embedding, metadata, sequence)
                    VALUES %s
                    """,
                    processed_chunks,
                    template="(%s, %s, %s::vector, %s, %s)"
                )
                
                return len(processed_chunks)
        except Exception as e:
            logger.error(f"Error adding chunks: {str(e)}")
            raise

    def batch_add_chunks(self, chunks_by_document: Dict[int, List[Dict[str, Any]]]) -> Dict[int, int]:
        """Add chunks for multiple documents in efficient batches.
        
        Args:
            chunks_by_document: Dictionary with document IDs as keys and chunk lists as values
            
        Returns:
            Dictionary with document IDs as keys and number of chunks added as values
        """
        results = {}
        for doc_id, chunks in chunks_by_document.items():
            try:
                chunks_added = self.add_chunks(doc_id, chunks)
                results[doc_id] = chunks_added
            except Exception as e:
                logger.error(f"Error adding chunks for document {doc_id}: {str(e)}")
                results[doc_id] = 0
                
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def search_similar_chunks(self, query: str, therapy_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query with improved retrieval.

        Args:
            query: Query text
            therapy_type: Optional filter for therapy type ('cbt' or 'dbt')
            limit: Maximum number of chunks to return

        Returns:
            List of chunks with similarity scores
        """
        query_embedding = self.generate_embedding(query)

        with self._get_cursor() as (_, cursor):
            # fetch top candidates without threshold
            sql = """
            SELECT tc.id, tc.text, td.therapy_type,
                   1 - (tc.embedding <=> %s::vector) AS similarity
              FROM therapy_chunks tc
              JOIN therapy_documents td ON tc.document_id = td.id
             WHERE 1=1
            """
            params = [query_embedding]
            if therapy_type:
                sql += " AND td.therapy_type = %s"
                params.append(therapy_type)
            sql += " ORDER BY similarity DESC LIMIT %s"
            params.append(self.max_retrieval_count * 2)
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # compute quantile threshold
        sims = [row[3] for row in rows]
        if sims:
            sims_sorted = sorted(sims, reverse=True)
            idx = max(0, min(len(sims_sorted)-1, int(len(sims_sorted) * self.similarity_quantile)))
            threshold_quantile = sims_sorted[idx]
        else:
            threshold_quantile = self.similarity_threshold

        # choose stronger of global vs quantile
        base_threshold = max(self.similarity_threshold, threshold_quantile)

        # filter by per-therapy cutoff
        filtered = []
        for id, text, ttype, sim in rows:
            cutoff = self.similarity_threshold_cbt if ttype=="cbt" else self.similarity_threshold_dbt
            if sim >= max(base_threshold, cutoff):
                filtered.append((id, text, ttype, sim))

        # limit and format results
        results = []
        for id, text, ttype, sim in filtered[:limit]:
            results.append({"id": id, "text": text, "therapy_type": ttype, "similarity": sim})
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, min=1, max=5),
        reraise=True
    )
    def _keyword_search(self, query: str, therapy_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform keyword-based search as complement to vector search."""
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        keyword_conditions = ' | '.join(keywords)

        with self._get_cursor() as (_, cursor):
            sql = """
            SELECT 
                tc.id,
                tc.text,
                tc.document_id,
                tc.metadata,
                td.therapy_type,
                ts_rank_cd(to_tsvector('english', tc.text), to_tsquery('english', %s)) AS rank
            FROM therapy_chunks tc
            JOIN therapy_documents td ON tc.document_id = td.id
            WHERE to_tsvector('english', tc.text) @@ to_tsquery('english', %s)
            """

            params = [keyword_conditions, keyword_conditions]

            if therapy_type:
                sql += " AND td.therapy_type = %s"
                params.append(therapy_type)

            sql += " ORDER BY rank DESC LIMIT %s"
            params.append(limit * 2)  # Get more for better merging

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                chunk_id, text, doc_id, metadata, therapy_type, rank = row
                # Scale rank to 0-1 range similar to cosine similarity
                scaled_similarity = min(rank / 10.0, 1.0)  # Normalize rank score

                result = {
                    "id": chunk_id,
                    "text": text,
                    "document_id": doc_id,
                    "therapy_type": therapy_type,
                    "similarity": scaled_similarity,
                    "metadata": metadata or {},
                    "source": "keyword"
                }
                results.append(result)

            return results

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query for text search."""
        # Remove stopwords and get meaningful terms
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 
                     'when', 'where', 'how', 'i', 'you', 'he', 'she', 'we', 'they', 'it', 'to', 'in',
                     'for', 'with', 'feel', 'feeling', 'felt', 'am', 'is', 'are', 'was', 'were', 'be'}

        # Normalize and tokenize
        words = re.findall(r'\b[a-z]{3,}\b', query.lower())
        keywords = [word for word in words if word not in stop_words]

        # Add word combinations for phrases (bigrams)
        tokens = query.lower().split()
        bigrams = []
        for i in range(len(tokens) - 1):
            w1 = tokens[i]
            w2 = tokens[i + 1]
            if len(w1) > 2 and len(w2) > 2 and w1 not in stop_words and w2 not in stop_words:
                bigrams.append(f"{w1} <-> {w2}")

        return keywords + bigrams[:3]  # Limit bigrams to avoid query complexity

    def _merge_search_results(self, vector_results: List[Dict], keyword_results: List[Dict]) -> List[Dict]:
        """Merge vector and keyword search results with weighted scoring."""
        # Create map of existing results by ID
        result_map = {r["id"]: r for r in vector_results}

        # Process keyword results
        for kr in keyword_results:
            if kr["id"] in result_map:
                # Existing result - blend the scores with weights
                existing = result_map[kr["id"]]
                vector_score = existing["similarity"] * self.semantic_weight
                keyword_score = kr["similarity"] * self.keyword_weight
                existing["similarity"] = vector_score + keyword_score
                existing["hybrid_score"] = True
            else:
                # New result - scale the keyword score
                kr["similarity"] = kr["similarity"] * self.keyword_weight
                kr["hybrid_score"] = True
                result_map[kr["id"]] = kr

        # Convert back to list and sort
        merged_results = list(result_map.values())
        merged_results.sort(key=lambda x: x["similarity"], reverse=True)

        return merged_results

    def _rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """Rerank results using more sophisticated factors."""
        if not results:
            return results

        # We'll implement a simple but effective reranking
        # 1. Extract key terms from the query
        query_terms = set(self._extract_keywords(query.lower()))
        if not query_terms:
            return results

        # 2. For each result, calculate term overlap and adjust scores
        for result in results:
            text = result["text"].lower()

            # Calculate term density
            term_matches = sum(1 for term in query_terms if term in text)
            term_density = term_matches / max(1, len(query_terms))

            # Check for paragraph structure and readability
            sentences = len(re.findall(r'[.!?]\s', text))
            readability_score = min(sentences / 20.0, 1.0)  # More sentences = more complete info

            # Combine original similarity with our new factors
            original_score = result["similarity"]
            result["similarity"] = original_score * 0.7 + term_density * 0.2 + readability_score * 0.1

        # Re-sort based on adjusted scores
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, min=1, max=5),
        reraise=True
    )
    def determine_therapy_approach(self, query: str) -> Tuple[str, float, List[Dict]]:
        """Determine which therapy approach is most appropriate with weighted voting.

        Args:
            query: User's query

        Returns:
            Tuple of (therapy_type, confidence_score, supporting_chunks)
        """
        # Get relevant chunks from both therapy types
        try:
            similar_chunks = self.search_similar_chunks(query, limit=5)

            if not similar_chunks:
                return "unknown", 0.0, []

            # Calculate weighted votes for each therapy type
            votes = {"cbt": 0.0, "dbt": 0.0}

            # Filter chunks with low similarity
            quality_chunks = [c for c in similar_chunks if c["similarity"] >= self.similarity_threshold]

            if not quality_chunks:
                # Fall back to best matches even if below threshold
                quality_chunks = similar_chunks[:2]

            # Calculate total similarity for normalization
            total_similarity = sum(chunk["similarity"] for chunk in quality_chunks)

            if total_similarity == 0:
                return "unknown", 0.0, []

            # Weighted voting based on similarity scores
            for chunk in quality_chunks:
                therapy = chunk["therapy_type"].lower()
                if therapy in votes:
                    # Weight vote by normalized similarity
                    votes[therapy] += chunk["similarity"] / total_similarity

            # Determine winner and calculate confidence
            cbt_score = votes.get("cbt", 0.0)
            dbt_score = votes.get("dbt", 0.0)

            if cbt_score > dbt_score:
                therapy_type = "cbt"
                # Calculate confidence - adjusted for stronger distinction
                raw_confidence = cbt_score / max(cbt_score + dbt_score, 1.0)
                confidence = self._calibrate_confidence(raw_confidence, cbt_score, dbt_score)
            else:
                therapy_type = "dbt"
                raw_confidence = dbt_score / max(cbt_score + dbt_score, 1.0)
                confidence = self._calibrate_confidence(raw_confidence, dbt_score, cbt_score)

            # Return with supporting chunks of the selected therapy
            supporting_chunks = [c for c in quality_chunks if c["therapy_type"].lower() == therapy_type]

            return therapy_type, confidence, supporting_chunks

        except Exception as e:
            logger.error(f"Error determining therapy approach: {str(e)}", exc_info=True)
            # More robust error handling with retry
            raise

    def _calibrate_confidence(self, raw_confidence: float, winner_score: float, loser_score: float) -> float:
        """Calibrate confidence scores to be more realistic and less overconfident."""
        # Apply sigmoid-like scaling to make confidence distribution more useful
        margin = winner_score - loser_score

        # Small margins should reduce confidence
        if margin < 0.1:
            return max(0.5, raw_confidence * 0.8)
        elif margin < 0.3:
            return min(0.9, raw_confidence * 1.1) 
        else:
            # Large margins can be more confident
            return min(0.95, raw_confidence * 1.2)


# Create instance for easy import
vector_store = VectorStore()

# chatbot/services/rag/vector_store.py
import re
import subprocess
import numpy as np
import psycopg2
import logging
import requests
import os
from typing import List, Dict, Any, Optional, Tuple
from psycopg2.extras import execute_values, Json
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)

class VectorStore:
    """Vector store for document embeddings using PostgreSQL with pgvector."""
    
    def __init__(self):
        """Initialize the vector store with database configuration."""
        self.db_config = {
            'dbname': settings.DATABASES['default']['NAME'],
            'user': settings.DATABASES['default']['USER'],
            'password': settings.DATABASES['default']['PASSWORD'],
            'host': settings.DATABASES['default']['HOST'],
            'port': settings.DATABASES['default']['PORT'],
        }
        self.embed_model = "nomic-embed-text:latest"  # version pinned
        self.embedding_dimension = 384  # Matches nomic-embed-text dimension
        self.gpu_layers = 50  # For GPU acceleration
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.setup_db()
        
    def setup_db(self):
        """Set up the database with necessary extensions and tables."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Enable pgvector extension
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS therapy_documents (
                    id SERIAL PRIMARY KEY,
                    therapy_type VARCHAR(50) NOT NULL,  -- 'cbt' or 'dbt'
                    document_name TEXT NOT NULL,
                    document_path TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
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
            
            conn.commit()
            cursor.close()
            conn.close()
            
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
            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text,
                    "options": {"num_gpu": self.gpu_layers}
                },
                timeout=30
            )
            response.raise_for_status()
            embedding = np.array(response.json()["embedding"])
            # If returned embedding has 768 dimensions but DB expects 1536, duplicate it.
            if embedding.shape[0] == 768:
                embedding = np.concatenate([embedding, embedding])
            return embedding
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            raise
    
    def add_document(self, therapy_type: str, document_name: str, document_path: str, metadata: Dict = None) -> int:
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
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO therapy_documents (therapy_type, document_name, document_path, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (therapy_type.lower(), document_name, document_path, Json(metadata)))
            
            document_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            return document_id
            
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise
    
    def add_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> int:
        """Add text chunks with embeddings to the store.
        
        Args:
            document_id: ID of the document these chunks belong to
            chunks: List of chunk dictionaries with text and metadata
            
        Returns:
            Number of chunks added
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Prepare data for bulk insert using concurrent processing for embeddings
            from concurrent.futures import ThreadPoolExecutor
            from tqdm import tqdm  # import tqdm locally
            
            texts = [chunk['text'] for chunk in chunks]
            # Generate embeddings concurrently with progress bar
            with ThreadPoolExecutor(max_workers=10) as executor:
                embeddings = list(tqdm(executor.map(self._get_embedding, texts),
                                         total=len(texts),
                                         desc="Processing Chunks",
                                         ncols=80,
                                         leave=False))
            
            chunk_data = []
            for i, chunk in enumerate(chunks):
                metadata = chunk.get('metadata', {})
                chunk_data.append((document_id, i, chunk['text'], embeddings[i].tolist(), Json(metadata)))
            
            # Bulk insert chunks
            execute_values(
                cursor,
                """
                INSERT INTO therapy_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
                VALUES %s
                ON CONFLICT (document_id, chunk_index) DO UPDATE 
                SET chunk_text = EXCLUDED.chunk_text,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
                """,
                chunk_data
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error adding chunks: {str(e)}")
            raise
    
    def search_similar_chunks(self, query: str, therapy_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query.
        
        Args:
            query: Search query
            therapy_type: Optional filter for therapy type ('cbt', 'dbt', or None for both)
            limit: Maximum number of results to return
            
        Returns:
            List of similar chunks with similarity scores
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Build query based on whether therapy_type is specified
            if therapy_type:
                sql = """
                    SELECT tc.chunk_text, tc.metadata, td.therapy_type, 
                           1 - (tc.embedding <=> %s::vector) as similarity
                    FROM therapy_chunks tc
                    JOIN therapy_documents td ON tc.document_id = td.id
                    WHERE td.therapy_type = %s
                    ORDER BY similarity DESC
                    LIMIT %s
                """
                cursor.execute(sql, (query_embedding.tolist(), therapy_type.lower(), limit))
            else:
                sql = """
                    SELECT tc.chunk_text, tc.metadata, td.therapy_type, 
                           1 - (tc.embedding <=> %s::vector) as similarity
                    FROM therapy_chunks tc
                    JOIN therapy_documents td ON tc.document_id = td.id
                    ORDER BY similarity DESC
                    LIMIT %s
                """
                cursor.execute(sql, (query_embedding.tolist(), limit))
            
            results = []
            for chunk_text, metadata, doc_therapy_type, similarity in cursor.fetchall():
                results.append({
                    'text': chunk_text,
                    'therapy_type': doc_therapy_type,
                    'metadata': metadata,
                    'similarity': float(similarity)
                })
            
            cursor.close()
            conn.close()
            
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
            cbt_chunks = self.search_similar_chunks(query, therapy_type='cbt', limit=3)
            dbt_chunks = self.search_similar_chunks(query, therapy_type='dbt', limit=3)
            
            # Calculate average similarity scores
            cbt_avg_score = sum(chunk['similarity'] for chunk in cbt_chunks) / len(cbt_chunks) if cbt_chunks else 0
            dbt_avg_score = sum(chunk['similarity'] for chunk in dbt_chunks) / len(dbt_chunks) if dbt_chunks else 0
            
            # Determine which approach has higher relevance
            if cbt_avg_score > dbt_avg_score:
                recommended_therapy = 'cbt'
                confidence = cbt_avg_score
                supporting_chunks = cbt_chunks
            else:
                recommended_therapy = 'dbt'
                confidence = dbt_avg_score
                supporting_chunks = dbt_chunks
            
            return recommended_therapy, confidence, supporting_chunks
            
        except Exception as e:
            logger.error(f"Error determining therapy approach: {str(e)}")
            return 'unknown', 0.0, []

# Create instance for easy import
vector_store = VectorStore()
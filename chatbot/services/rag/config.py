# chatbot/services/rag/config.py
import os
from django.conf import settings

# Base directory setup
BASE_DIR = settings.BASE_DIR

# Embedding model settings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", 1024)
)  # BGE-M3 uses 1024 dimensions

# Directory and file paths
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "chatbot", "data"))
CBT_PDF_PATH = os.getenv(
    "CBT_PDF_PATH",
    os.path.join(
        DATA_DIR,
        "cbt",
        "Cognitive therapy _ basics and beyond -- Judith S. Beck Phd -- ( WeLib.org ).pdf",
    ),
)
DBT_PDF_PATH = os.getenv(
    "DBT_PDF_PATH",
    os.path.join(
        DATA_DIR,
        "dbt",
        "The Dialectical Behavior Therapy Skills Workbook ( PDFDrive ).pdf",
    ),
)

# Document metadata
CBT_METADATA = {
    "title": "Cognitive Therapy: Basics and Beyond",
    "author": "Judith S. Beck",
    "therapy_type": "Cognitive Behavioral Therapy",
    "description": "A foundational text on cognitive therapy principles and techniques",
}

DBT_METADATA = {
    "title": "The Dialectical Behavior Therapy Skills Workbook",
    "therapy_type": "Dialectical Behavior Therapy",
    "description": "A practical workbook for DBT skills and techniques",
}

# Chunking settings
CHUNK_SIZE = int(
    os.getenv("CHUNK_SIZE", 800)
)  # Changed from 1000 to 800 for more granular chunks
CHUNK_OVERLAP = int(
    os.getenv("CHUNK_OVERLAP", 150)
)  # Changed from 200 to 150 for better balance

# Vector search settings
SIMILARITY_THRESHOLD = float(
    os.getenv("SIMILARITY_THRESHOLD", 0.7)
)
MINIMUM_CONFIDENCE_THRESHOLD = float(
    os.getenv("MINIMUM_CONFIDENCE_THRESHOLD", 0.65)
)
SIMILARITY_DIFFERENCE_THRESHOLD = float(
    os.getenv("SIMILARITY_DIFFERENCE_THRESHOLD", 0.05)
)

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", 35))  # Reduced to 35 to fit in 6GB VRAM

#chatbot/services/rag/config.py
import os
from django.conf import settings

# Vector database settings
VECTOR_DB_CONFIG = {
    "dbname": settings.DATABASES["default"]["NAME"],
    "user": settings.DATABASES["default"]["USER"],
    "password": settings.DATABASES["default"]["PASSWORD"],
    "host": settings.DATABASES["default"]["HOST"],
    "port": settings.DATABASES["default"]["PORT"],
}

# Embedding model settings
EMBEDDING_MODEL = getattr(settings, "EMBED_MODEL", "text-embedding-ada-002")
EMBEDDING_DIMENSION = 1536  # Default for OpenAI's text-embedding-ada-002

# PDF document paths
DATA_DIR = os.path.join(settings.BASE_DIR, "chatbot", "data")
CBT_PDF_PATH = os.path.join(
    DATA_DIR,
    "Cognitive therapy _ basics and beyond -- Judith S. Beck Phd -- ( WeLib.org ).pdf",
)
DBT_PDF_PATH = os.path.join(
    DATA_DIR, "The Dialectical Behavior Therapy Skills Workbook ( PDFDrive ).pdf"
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
CHUNK_SIZE = 1000  # Characters
CHUNK_OVERLAP = 200  # Characters

# API keys - try to get from settings or environment
OPENAI_API_KEY = getattr(
    settings, "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")
)

# Therapy selection thresholds
MINIMUM_CONFIDENCE_THRESHOLD = (
    0.6  # Minimum confidence score to recommend a therapy approach
)
SIMILARITY_DIFFERENCE_THRESHOLD = 0.05  # Minimum difference in similarity scores to recommend one therapy over another

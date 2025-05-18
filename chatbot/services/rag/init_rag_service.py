# chatbot/services/rag/init_rag_service.py
import os
import logging
import subprocess
import sys
from django.conf import settings

logger = logging.getLogger(__name__)


def setup_environment():
    """Setup the environment for the RAG service."""
    try:
        # Install required packages
        requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
        if os.path.exists(requirements_path):
            logger.info("Installing RAG service dependencies...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", requirements_path]
            )
            logger.info("Dependencies installed successfully")
        else:
            logger.warning("Requirements file not found at %s", requirements_path)

        # Check if OpenAI API key is configured
        if not hasattr(settings, "OPENAI_API_KEY") or not settings.OPENAI_API_KEY:
            logger.warning(
                "OpenAI API key not found in settings. RAG service may not function properly."
            )

        # Check if pgvector extension is available
        try:
            import psycopg2

            conn_params = settings.DATABASES["default"]
            conn = psycopg2.connect(
                dbname=conn_params["NAME"],
                user=conn_params["USER"],
                password=conn_params["PASSWORD"],
                host=conn_params["HOST"],
                port=conn_params["PORT"],
            )

            # Check if pgvector extension exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
            )
            has_pgvector = cursor.fetchone()[0]

            if not has_pgvector:
                logger.warning(
                    "pgvector extension not available in PostgreSQL. Please install it for vector search functionality."
                )
            else:
                # Check if extension is already created
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                )
                is_installed = cursor.fetchone()[0]
                if not is_installed:
                    logger.info("Creating pgvector extension...")
                    try:
                        cursor.execute("CREATE EXTENSION vector")
                        conn.commit()
                        logger.info("pgvector extension created successfully")
                    except Exception as e:
                        logger.error("Error creating pgvector extension: %s", str(e))
                else:
                    logger.info("pgvector extension already installed")

            conn.close()
        except Exception as e:
            logger.error("Error checking PostgreSQL configuration: %s", str(e))

        # Make sure PDF files exist
        data_dir = os.path.join(settings.BASE_DIR, "chatbot", "data")
        cbt_path = os.path.join(
            data_dir,
            "Cognitive therapy _ basics and beyond -- Judith S. Beck Phd -- ( WeLib.org ).pdf",
        )
        dbt_path = os.path.join(
            data_dir,
            "The Dialectical Behavior Therapy Skills Workbook ( PDFDrive ).pdf",
        )

        if not os.path.exists(cbt_path):
            logger.warning("CBT PDF file not found at: %s", cbt_path)
        else:
            logger.info("CBT PDF file found at: %s", cbt_path)

        if not os.path.exists(dbt_path):
            logger.warning("DBT PDF file not found at: %s", dbt_path)
        else:
            logger.info("DBT PDF file found at: %s", dbt_path)

        return True
    except Exception as e:
        logger.error("Error setting up RAG environment: %s", str(e))
        return False


def initialize_rag_service():
    """Initialize the RAG service."""
    if setup_environment():
        logger.info("RAG environment setup complete")
        # Import and return the therapy_rag_service
        try:
            from .therapy_rag_service import therapy_rag_service

            logger.info("RAG service imported successfully")
            return therapy_rag_service
        except Exception as e:
            logger.error("Error importing therapy_rag_service: %s", str(e))
            return None
    else:
        logger.error("RAG environment setup failed")
        return None


# Auto-initialize when imported
rag_service = initialize_rag_service()

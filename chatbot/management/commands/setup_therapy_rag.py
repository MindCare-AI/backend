#chatbot/management/commands/setup_therapy_rag.py 
import logging
import subprocess
from django.core.management.base import BaseCommand
from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.gpu_utils import verify_gpu_support

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up and index therapy documents for the RAG system"

    def handle(self, *args, **kwargs):
        try:
            # Verify GPU availability
            verify_gpu_support()

            # First, pull the optimized Ollama model without unsupported GPU flags
            self.stdout.write(
                self.style.NOTICE("Pulling optimized Ollama model...")
            )
            # Use subprocess.run to capture errors
            result = subprocess.run(
                ["ollama", "pull", "nomic-embed-text:latest"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                err_text = result.stderr.lower() + result.stdout.lower()
                if "lookup ollama" in err_text:
                    error_msg = (
                        "DNS resolution error for host 'ollama'. "
                        "Please update OLLAMA_HOST in your .env file to 'http://localhost:11434' "
                        "or ensure that the hostname 'ollama' is resolvable."
                    )
                    self.stderr.write(self.style.ERROR(error_msg))
                    raise Exception(error_msg)
                else:
                    self.stderr.write(self.style.ERROR(result.stderr))
                    raise Exception(result.stderr)
            self.stdout.write(
                self.style.SUCCESS("Embedding model pulled successfully!")
            )

            self.stdout.write(
                self.style.NOTICE("Starting therapy document indexing...")
            )
            results = therapy_rag_service.setup_and_index_documents()

            # Display results in a readable format
            self.stdout.write(
                self.style.SUCCESS("Therapy documents indexed successfully!")
            )
            self.stdout.write("CBT Document:")
            self.stdout.write(f"  - Document ID: {results['cbt']['document_id']}")
            self.stdout.write(f"  - Chunks added: {results['cbt']['chunks_added']}")
            self.stdout.write(
                f"  - Text length: {results['cbt']['text_length']} characters"
            )

            self.stdout.write("DBT Document:")
            self.stdout.write(f"  - Document ID: {results['dbt']['document_id']}")
            self.stdout.write(f"  - Chunks added: {results['dbt']['chunks_added']}")
            self.stdout.write(
                f"  - Text length: {results['dbt']['text_length']} characters"
            )

            self.stdout.write(
                self.style.SUCCESS("The therapy RAG system is ready to use!")
            )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error setting up therapy RAG system: {str(e)}")
            )
            logger.error(f"Error in setup_therapy_rag command: {str(e)}", exc_info=True)

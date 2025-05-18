# chatbot/management/commands/setup_therapy_rag.py
import logging
import time
import datetime
import os
from django.core.management.base import BaseCommand
from django.core import management
from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.gpu_utils import verify_gpu_support
from tqdm import tqdm  # Import tqdm for progress tracking

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up and index therapy documents for the RAG system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-model-pull",
            action="store_true",
            help="Skip pulling the embedding model (use if model is already pulled)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=int(os.getenv("RAG_BATCH_SIZE", 10)),  # Changed from 20 to 10
            help="Number of chunks to process in each batch (default from RAG_BATCH_SIZE env var or 10)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=int(os.getenv("RAG_SETUP_TIMEOUT", 1200)),
            help="Timeout in seconds for the entire operation (default from RAG_SETUP_TIMEOUT env var or 1200)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed progress information including each chunk",
        )

    def handle(self, *args, **kwargs):
        start_time = time.time()
        batch_size = kwargs.get("batch_size", 5)

        # Store original settings to restore later
        from chatbot.services.rag.vector_store import vector_store

        original_batch_size = getattr(vector_store, "BATCH_SIZE", 10)

        try:
            # Set batch size if specified
            if hasattr(vector_store, "BATCH_SIZE"):
                vector_store.BATCH_SIZE = batch_size

            # Verify GPU availability
            gpu_info = verify_gpu_support()
            if gpu_info:
                # dict with details or simple True
                if isinstance(gpu_info, dict):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"🚀 GPU ENABLED: {gpu_info.get('details', '')}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "🚀 GPU detected (no additional details available)"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️ GPU not detected, using CPU only. This will be significantly slower."
                    )
                )

            # Pull the embedding model if not skipped
            if not kwargs.get("skip_model_pull"):
                self.stdout.write(
                    self.style.NOTICE("Pulling optimized embedding model...")
                )
                try:
                    # Use the separate management command with a timeout
                    management.call_command("pull_embedding_model", timeout=300)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"Error pulling embedding model: {str(e)}")
                    )
                    self.stderr.write(
                        self.style.WARNING(
                            "Continuing with indexing, but it might fail if the model isn't available"
                        )
                    )
            else:
                self.stdout.write(self.style.NOTICE("Skipping model pull as requested"))

            self.stdout.write(
                self.style.NOTICE("Starting therapy document indexing process...")
            )

            # Display real-time clock
            start_datetime = datetime.datetime.now()
            self.stdout.write(
                f"Start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Show final GPU status
            gpu_info = verify_gpu_support()
            if gpu_info:
                if isinstance(gpu_info, dict):
                    details = gpu_info.get("details", "")
                else:
                    details = ""
                self.stdout.write(self.style.NOTICE(f"GPU usage: ENABLED {details}"))
            else:
                self.stdout.write(self.style.NOTICE("GPU usage: DISABLED"))

            self.stdout.write("\n📋 Setup Performance Tips:")
            self.stdout.write(
                "  - To improve extraction speed, install spaCy model: python manage.py download_spacy_model"
            )
            self.stdout.write(
                "  - For faster embedding, increase GPU layers in .env: OLLAMA_NUM_GPU=75"
            )
            self.stdout.write(
                "  - Set smaller chunk size for lighter processing: CHUNK_SIZE=800\n"
            )

            self.stdout.write("\n📄 Extracting therapy documents - please wait...")
            self.stdout.write(
                "   This step extracts text from PDF files and prepares them for embedding."
            )

            # Remove custom progress callback to allow internal tqdm in therapy_rag_service.extract_documents to work
            extracted_docs = therapy_rag_service.extract_documents()

            # Count total chunks for better progress reporting
            total_chunks = 0
            for therapy_type in extracted_docs:
                for doc in extracted_docs[therapy_type]:
                    total_chunks += len(doc["chunks"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Document extraction complete! Found {total_chunks} total chunks to process"
                )
            )

            self.stdout.write(
                self.style.NOTICE(
                    f"Starting document indexing and embedding - processing {total_chunks} chunks"
                )
            )
            self.stdout.write(
                "This step embeds each chunk using the neural network model and stores in the database.\n"
                "It may take significant time (10-30 minutes) depending on your hardware."
            )

            # Process with progress updates using tqdm
            results_by_type = {"cbt": [], "dbt": []}  # Initialize results structure
            indexing_results = therapy_rag_service.index_documents(extracted_docs)

            with tqdm(
                total=total_chunks, desc="Indexing chunks", unit="chunk", ncols=100
            ) as progress_bar:
                for therapy_type in ["cbt", "dbt"]:
                    for result in indexing_results.get(therapy_type, []):
                        results_by_type[therapy_type].append(result)
                        progress_bar.update(1)

            # Display results in a readable format
            total_elapsed = time.time() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f"Therapy documents indexed successfully in {total_elapsed:.1f} seconds!"
                )
            )

            # Show per-document stats
            cbt_chunks = sum(
                doc.get("chunks_added", 0) for doc in results_by_type["cbt"]
            )
            dbt_chunks = sum(
                doc.get("chunks_added", 0) for doc in results_by_type["dbt"]
            )

            self.stdout.write(f"CBT Documents: {len(results_by_type['cbt'])}")
            self.stdout.write(f"- Total chunks: {cbt_chunks}")

            self.stdout.write(f"DBT Documents: {len(results_by_type['dbt'])}")
            self.stdout.write(f"- Total chunks: {dbt_chunks}")

            self.stdout.write(f"Total chunks added: {cbt_chunks + dbt_chunks}")

            end_datetime = datetime.datetime.now()
            duration = end_datetime - start_datetime
            self.stdout.write(f"Total processing time: {duration}")

            self.stdout.write(
                self.style.SUCCESS("The therapy RAG system is ready to use!")
            )

        except TimeoutError as e:
            self.stderr.write(self.style.ERROR(f"Operation timed out: {str(e)}"))
            self.stderr.write(
                self.style.WARNING(
                    "Try running with --skip-model-pull if the model is already downloaded"
                )
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error setting up therapy RAG system: {str(e)}")
            )
            logger.error(f"Error in setup_therapy_rag command: {str(e)}", exc_info=True)
        finally:
            # Restore original settings
            if hasattr(vector_store, "BATCH_SIZE"):
                vector_store.BATCH_SIZE = original_batch_size

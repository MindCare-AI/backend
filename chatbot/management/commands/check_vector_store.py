# chatbot/management/commands/check_vector_store.py
import os
import json
import logging
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from tqdm import tqdm

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check status of local vector store and display statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Verify embeddings integrity (may take longer)",
        )

    def handle(self, *args, **kwargs):
        start_time = time.time()
        chunks_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "chunks")

        verify = kwargs.get("verify", False)

        if not os.path.exists(chunks_dir):
            self.stderr.write(self.style.ERROR(f"Vector store not found: {chunks_dir}"))
            return

        # Check config file
        config_path = os.path.join(chunks_dir, "config.json")
        if not os.path.exists(config_path):
            self.stderr.write(
                self.style.ERROR(f"Vector store configuration not found: {config_path}")
            )
            return

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            self.stdout.write(self.style.SUCCESS("Vector Store Configuration:"))
            self.stdout.write(f"- Version: {config.get('version', 'unknown')}")
            self.stdout.write(f"- Created: {config.get('created_at', 'unknown')}")
            self.stdout.write(f"- GPU Enabled: {config.get('gpu_enabled', False)}")
            self.stdout.write(
                f"- Embedding Model: {config.get('embedding_model', 'unknown')}"
            )
            self.stdout.write(
                f"- Embedding Dimension: {config.get('embedding_dimension', 'unknown')}"
            )

            # Check document index
            doc_index_path = os.path.join(chunks_dir, "index", "documents.json")
            if not os.path.exists(doc_index_path):
                self.stderr.write(
                    self.style.ERROR(f"Document index not found: {doc_index_path}")
                )
                return

            with open(doc_index_path, "r") as f:
                document_index = json.load(f)

            # Check therapy indexes
            cbt_index_path = os.path.join(chunks_dir, "index", "cbt_chunks.json")
            dbt_index_path = os.path.join(chunks_dir, "index", "dbt_chunks.json")

            if not os.path.exists(cbt_index_path) or not os.path.exists(dbt_index_path):
                self.stderr.write(
                    self.style.WARNING("One or more therapy indexes not found")
                )

            cbt_chunks = []
            dbt_chunks = []
            if os.path.exists(cbt_index_path):
                with open(cbt_index_path, "r") as f:
                    cbt_chunks = json.load(f)

            if os.path.exists(dbt_index_path):
                with open(dbt_index_path, "r") as f:
                    dbt_chunks = json.load(f)

            # Display statistics
            document_count = len(document_index)
            cbt_document_count = len(
                [
                    doc
                    for doc in document_index.values()
                    if doc.get("therapy_type") == "cbt"
                ]
            )
            dbt_document_count = len(
                [
                    doc
                    for doc in document_index.values()
                    if doc.get("therapy_type") == "dbt"
                ]
            )

            self.stdout.write("\nVector Store Statistics:")
            self.stdout.write(f"- Total Documents: {document_count}")
            self.stdout.write(f"  - CBT Documents: {cbt_document_count}")
            self.stdout.write(f"  - DBT Documents: {dbt_document_count}")
            self.stdout.write(f"- Total Chunks: {len(cbt_chunks) + len(dbt_chunks)}")
            self.stdout.write(f"  - CBT Chunks: {len(cbt_chunks)}")
            self.stdout.write(f"  - DBT Chunks: {len(dbt_chunks)}")

            # Check actual chunk files
            cbt_files = (
                os.listdir(os.path.join(chunks_dir, "cbt"))
                if os.path.exists(os.path.join(chunks_dir, "cbt"))
                else []
            )
            dbt_files = (
                os.listdir(os.path.join(chunks_dir, "dbt"))
                if os.path.exists(os.path.join(chunks_dir, "dbt"))
                else []
            )

            self.stdout.write("\nFile System Check:")
            self.stdout.write(f"- CBT Chunk Files: {len(cbt_files)}")
            self.stdout.write(f"- DBT Chunk Files: {len(dbt_files)}")

            if len(cbt_files) != len(cbt_chunks) or len(dbt_files) != len(dbt_chunks):
                self.stdout.write(
                    self.style.WARNING("⚠️ Mismatch between indexes and files on disk!")
                )

            # Check for integrity issues
            if verify:
                self.stdout.write("\nVerifying chunk integrity...")

                broken_chunks = 0
                missing_embeddings = 0

                # Check CBT chunks
                for chunk_id in tqdm(cbt_chunks, desc="Verifying CBT chunks"):
                    chunk_path = os.path.join(chunks_dir, "cbt", f"{chunk_id}.json")
                    if not os.path.exists(chunk_path):
                        broken_chunks += 1
                        continue

                    try:
                        with open(chunk_path, "r") as f:
                            chunk_data = json.load(f)

                        if "embedding" not in chunk_data or not chunk_data["embedding"]:
                            missing_embeddings += 1
                    except Exception:
                        broken_chunks += 1

                # Check DBT chunks
                for chunk_id in tqdm(dbt_chunks, desc="Verifying DBT chunks"):
                    chunk_path = os.path.join(chunks_dir, "dbt", f"{chunk_id}.json")
                    if not os.path.exists(chunk_path):
                        broken_chunks += 1
                        continue

                    try:
                        with open(chunk_path, "r") as f:
                            chunk_data = json.load(f)

                        if "embedding" not in chunk_data or not chunk_data["embedding"]:
                            missing_embeddings += 1
                    except Exception:
                        broken_chunks += 1

                self.stdout.write("\nIntegrity Check Results:")
                if broken_chunks == 0 and missing_embeddings == 0:
                    self.stdout.write(self.style.SUCCESS("✓ All chunks are valid"))
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Found {broken_chunks} broken chunks")
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Found {missing_embeddings} chunks with missing embeddings"
                        )
                    )
                    self.stdout.write(
                        "\nRun 'python manage.py fix_local_vector_store' to attempt repairs"
                    )

            elapsed_time = time.time() - start_time
            self.stdout.write(f"\nCheck completed in {elapsed_time:.2f} seconds")

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error checking vector store: {str(e)}")
            )
            logger.error("Error checking vector store", exc_info=True)

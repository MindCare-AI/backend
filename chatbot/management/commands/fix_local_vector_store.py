# chatbot/management/commands/fix_local_vector_store.py
"""Command to create a config file for the local vector store."""

import os
import json
import logging
import time
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fix the local vector store configuration"

    def handle(self, *args, **kwargs):
        chunks_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "chunks")

        if not os.path.exists(chunks_dir):
            self.stderr.write(
                self.style.ERROR(f"Chunks directory not found: {chunks_dir}")
            )
            return

        # Check for index directory
        index_dir = os.path.join(chunks_dir, "index")
        if not os.path.exists(index_dir):
            self.stdout.write("Creating index directory...")
            os.makedirs(index_dir, exist_ok=True)

        # Check for therapy type directories
        cbt_dir = os.path.join(chunks_dir, "cbt")
        dbt_dir = os.path.join(chunks_dir, "dbt")

        if not os.path.exists(cbt_dir):
            self.stdout.write("Creating CBT directory...")
            os.makedirs(cbt_dir, exist_ok=True)

        if not os.path.exists(dbt_dir):
            self.stdout.write("Creating DBT directory...")
            os.makedirs(dbt_dir, exist_ok=True)

        # Count documents and chunks
        cbt_chunks = []
        dbt_chunks = []
        if os.path.exists(cbt_dir):
            cbt_chunks = [
                f.replace(".json", "")
                for f in os.listdir(cbt_dir)
                if f.endswith(".json")
            ]

        if os.path.exists(dbt_dir):
            dbt_chunks = [
                f.replace(".json", "")
                for f in os.listdir(dbt_dir)
                if f.endswith(".json")
            ]

        # Create/update document index
        document_index_path = os.path.join(index_dir, "documents.json")
        document_index = {}

        if os.path.exists(document_index_path):
            try:
                with open(document_index_path, "r") as f:
                    document_index = json.load(f)
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(f"Could not load existing document index: {e}")
                )

        # If we don't have a document index or it's empty, create a placeholder
        if not document_index:
            document_index = {
                "cbt_1": {
                    "id": "cbt_1",
                    "therapy_type": "cbt",
                    "title": "Cognitive Behavioral Therapy Documents",
                    "file_path": "",
                    "metadata": {
                        "title": "Cognitive Behavioral Therapy",
                        "therapy_type": "Cognitive Behavioral Therapy",
                        "description": "CBT techniques and materials",
                    },
                    "chunk_count": len(cbt_chunks),
                },
                "dbt_1": {
                    "id": "dbt_1",
                    "therapy_type": "dbt",
                    "title": "Dialectical Behavior Therapy Documents",
                    "file_path": "",
                    "metadata": {
                        "title": "Dialectical Behavior Therapy",
                        "therapy_type": "Dialectical Behavior Therapy",
                        "description": "DBT techniques and materials",
                    },
                    "chunk_count": len(dbt_chunks),
                },
            }

        # Write document index
        with open(document_index_path, "w") as f:
            json.dump(document_index, f, indent=2)

        # Write chunk indexes
        with open(os.path.join(index_dir, "cbt_chunks.json"), "w") as f:
            json.dump(cbt_chunks, f)

        with open(os.path.join(index_dir, "dbt_chunks.json"), "w") as f:
            json.dump(dbt_chunks, f)

        # Create config file
        config_path = os.path.join(chunks_dir, "config.json")

        config = {
            "version": "1.0",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chunk_count": len(cbt_chunks) + len(dbt_chunks),
            "document_count": len(document_index),
            "therapy_counts": {
                "cbt": sum(1 for k in document_index if k.startswith("cbt")),
                "dbt": sum(1 for k in document_index if k.startswith("dbt")),
            },
            "therapy_chunk_counts": {"cbt": len(cbt_chunks), "dbt": len(dbt_chunks)},
            "embedding_model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest"),
            "embedding_dimension": int(os.getenv("EMBEDDING_DIMENSION", 768)),
            "gpu_enabled": True,
        }

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f"Fixed vector store configuration. Found {len(cbt_chunks)} CBT chunks and {len(dbt_chunks)} DBT chunks."
            )
        )

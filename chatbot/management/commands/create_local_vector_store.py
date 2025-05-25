# chatbot/management/commands/create_local_vector_store.py
import os
import json
import logging
import time
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from tqdm import tqdm
from chatbot.services.rag.vector_store import vector_store
from chatbot.services.rag.gpu_utils import verify_gpu_support

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create a local vector store from indexed documents"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of chunks to process in each batch",
        )
        parser.add_argument(
            "--max-chunks",
            type=int,
            default=None,
            help="Maximum number of chunks per therapy type (None for all)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of local vector store if it exists",
        )

    def handle(self, *args, **kwargs):
        start_time = time.time()
        index_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "indexed")
        chunks_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "chunks")

        # Check GPU availability for better embedding generation
        gpu_info = verify_gpu_support()
        if gpu_info and isinstance(gpu_info, dict) and gpu_info.get("using_gpu"):
            self.stdout.write(
                self.style.SUCCESS(f"🚀 GPU ENABLED: {gpu_info.get('details', '')}")
            )

            # Optimize GPU memory usage by setting higher layers
            # Maximum performance by increasing GPU layers for Ollama
            os.environ["OLLAMA_NUM_GPU"] = str(os.getenv("OLLAMA_NUM_GPU", "80"))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set GPU layers to {os.environ['OLLAMA_NUM_GPU']} for maximum performance"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ CPU ONLY MODE: No GPU detected, processing will be slower"
                )
            )

        batch_size = kwargs.get("batch_size", 50)
        max_chunks = kwargs.get("max_chunks")
        force = kwargs.get("force", False)

        if not os.path.exists(index_dir):
            self.stderr.write(
                self.style.ERROR(f"Index directory not found: {index_dir}")
            )
            return

        # Create chunks directory structure
        if os.path.exists(chunks_dir):
            if force:
                self.stdout.write(f"Removing existing chunks directory: {chunks_dir}")
                shutil.rmtree(chunks_dir)
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Chunks directory already exists: {chunks_dir}. Use --force to recreate."
                    )
                )
                return

        os.makedirs(chunks_dir, exist_ok=True)
        os.makedirs(os.path.join(chunks_dir, "cbt"), exist_ok=True)
        os.makedirs(os.path.join(chunks_dir, "dbt"), exist_ok=True)

        # Create directory for document index
        os.makedirs(os.path.join(chunks_dir, "index"), exist_ok=True)

        json_files = [f for f in os.listdir(index_dir) if f.endswith(".json")]

        if not json_files:
            self.stderr.write(self.style.ERROR(f"No JSON files found in {index_dir}"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Found {len(json_files)} indexed document files")
        )

        # Track overall statistics
        total_docs = 0
        total_chunks = 0
        therapy_counts = {"cbt": 0, "dbt": 0}
        therapy_chunk_counts = {"cbt": 0, "dbt": 0}

        # Create document index file to keep track of all documents
        document_index = {}

        # Process each JSON file
        with tqdm(
            total=len(json_files), desc="Processing document files", unit="file"
        ) as progress_bar:
            for json_file in json_files:
                try:
                    file_path = os.path.join(index_dir, json_file)
                    with open(file_path, "r") as f:
                        doc_data = json.load(f)

                    therapy = doc_data.get("therapy", "unknown")
                    if therapy not in ["cbt", "dbt"]:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Unknown therapy type '{therapy}' in {json_file}, skipping"
                            )
                        )
                        progress_bar.update(1)
                        continue

                    # Create document entry
                    doc_id = f"{therapy}_{total_docs + 1}"
                    title = doc_data.get("filename", "Untitled")

                    # Add document to index
                    document_index[doc_id] = {
                        "id": doc_id,
                        "therapy_type": therapy,
                        "title": title,
                        "file_path": doc_data.get("pdf_path", ""),
                        "metadata": doc_data.get("metadata", {}),
                        "chunk_count": 0,
                    }

                    total_docs += 1
                    therapy_counts[therapy] += 1

                    # Process chunks
                    chunks = doc_data.get("chunks", [])

                    # Apply chunk limit if specified
                    if max_chunks is not None:
                        # Check if we've already processed enough chunks for this therapy type
                        if therapy_chunk_counts[therapy] >= max_chunks:
                            self.stdout.write(
                                f"Skipping remaining chunks for {therapy} (reached limit of {max_chunks})"
                            )
                            progress_bar.update(1)
                            continue

                        # Calculate how many more we can process
                        remaining_slots = max_chunks - therapy_chunk_counts[therapy]
                        if len(chunks) > remaining_slots:
                            self.stdout.write(
                                f"Limiting chunks for {title} to {remaining_slots}/{len(chunks)}"
                            )
                            chunks = chunks[:remaining_slots]

                    # Process chunks in batches
                    chunk_count_this_doc = 0

                    for i in range(0, len(chunks), batch_size):
                        batch = chunks[i : i + batch_size]
                        batch_count = 0

                        # Pre-process batch texts for embedding
                        batch_texts = []
                        batch_chunks = []

                        for j, chunk in enumerate(batch):
                            text = chunk.get("text", "")
                            if not text:
                                continue

                            chunk_id = f"{doc_id}_chunk_{i+j}"
                            batch_texts.append(text)
                            batch_chunks.append(
                                {
                                    "id": chunk_id,
                                    "document_id": doc_id,
                                    "text": text,
                                    "metadata": {
                                        "page": chunk.get("page", 0),
                                        "source": title,
                                        "therapy_type": therapy,
                                    },
                                    "sequence": i + j,
                                }
                            )

                        # Batch GPU processing - more efficient for GPU
                        if batch_texts:
                            self.stdout.write(
                                f"Processing batch of {len(batch_texts)} embeddings with GPU..."
                            )

                            # Generate embeddings in batches for better GPU utilization
                            # For each chunk in the current batch
                            for idx, text in enumerate(batch_texts):
                                # Generate embedding with GPU acceleration
                                embedding = vector_store.generate_embedding(text)

                                # Add embedding to chunk data
                                batch_chunks[idx]["embedding"] = embedding

                        # Process each chunk in the batch
                        for chunk_data in batch_chunks:
                            # Save chunk to file
                            chunk_path = os.path.join(
                                chunks_dir, therapy, f"{chunk_data['id']}.json"
                            )
                            with open(chunk_path, "w") as f:
                                json.dump(chunk_data, f)

                            batch_count += 1
                            chunk_count_this_doc += 1

                    # Update document index with chunk count
                    document_index[doc_id]["chunk_count"] = chunk_count_this_doc
                    therapy_chunk_counts[therapy] += chunk_count_this_doc
                    total_chunks += chunk_count_this_doc

                    progress_bar.set_postfix(docs=total_docs, chunks=total_chunks)
                    progress_bar.update(1)

                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"Error processing {json_file}: {str(e)}")
                    )
                    logger.error(f"Error processing {json_file}", exc_info=True)
                    progress_bar.update(1)

        # Save document index
        with open(os.path.join(chunks_dir, "index", "documents.json"), "w") as f:
            json.dump(document_index, f, indent=2)

        # Create therapy indexes for faster lookup
        cbt_chunks = [
            f.replace(".json", "") for f in os.listdir(os.path.join(chunks_dir, "cbt"))
        ]
        dbt_chunks = [
            f.replace(".json", "") for f in os.listdir(os.path.join(chunks_dir, "dbt"))
        ]

        with open(os.path.join(chunks_dir, "index", "cbt_chunks.json"), "w") as f:
            json.dump(cbt_chunks, f)

        with open(os.path.join(chunks_dir, "index", "dbt_chunks.json"), "w") as f:
            json.dump(dbt_chunks, f)

        # Create a config file
        config = {
            "version": "1.0",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chunk_count": total_chunks,
            "document_count": total_docs,
            "therapy_counts": therapy_counts,
            "therapy_chunk_counts": therapy_chunk_counts,
            "embedding_model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest"),
            "embedding_dimension": int(os.getenv("EMBEDDING_DIMENSION", 768)),
            "gpu_enabled": bool(gpu_info and gpu_info.get("using_gpu", False)),
        }

        with open(os.path.join(chunks_dir, "config.json"), "w") as f:
            json.dump(config, f, indent=2)

        # Display final statistics
        elapsed_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"Local vector store created successfully in {elapsed_time:.1f} seconds!"
            )
        )
        self.stdout.write(f"CBT Documents: {therapy_counts['cbt']}")
        self.stdout.write(f"- Total chunks: {therapy_chunk_counts['cbt']}")
        self.stdout.write(f"DBT Documents: {therapy_counts['dbt']}")
        self.stdout.write(f"- Total chunks: {therapy_chunk_counts['dbt']}")
        self.stdout.write(f"Total documents: {total_docs}")
        self.stdout.write(f"Total chunks: {total_chunks}")
        self.stdout.write(f"\nLocal vector store created at: {chunks_dir}")
        self.stdout.write(
            "Use --max-chunks option to limit chunks per therapy type if needed."
        )

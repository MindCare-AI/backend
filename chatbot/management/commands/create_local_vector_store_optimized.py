# chatbot/management/commands/create_local_vector_store_optimized.py
import os
import json
import logging
import time
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from tqdm import tqdm
import concurrent.futures
from chatbot.services.rag.vector_store import vector_store
from chatbot.services.rag.gpu_utils import verify_gpu_support

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create a local vector store from indexed documents with optimized GPU performance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,  # Increased default batch size for better GPU utilization
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
        parser.add_argument(
            "--parallel",
            type=int,
            default=2,  # Default parallel workers
            help="Number of parallel processing workers",
        )
        parser.add_argument(
            "--max-docs",
            type=int,
            default=None,
            help="Maximum number of documents to process (for testing)",
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

        batch_size = kwargs.get("batch_size", 100)
        max_chunks = kwargs.get("max_chunks")
        force = kwargs.get("force", False)
        max_docs = kwargs.get("max_docs")
        parallel_workers = kwargs.get("parallel", 2)

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

        # Limit document count if specified (for testing)
        if max_docs is not None and max_docs > 0:
            json_files = json_files[:max_docs]
            self.stdout.write(f"Limited to processing {max_docs} documents")

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

        # Load all documents first to group similar ones for better batch processing
        all_documents = []
        docs_by_therapy = {"cbt": [], "dbt": []}

        # Preload document data
        for json_file in tqdm(json_files, desc="Loading document metadata"):
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
                    continue

                doc_data["file_name"] = json_file
                all_documents.append(doc_data)
                docs_by_therapy[therapy].append(doc_data)

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error loading {json_file}: {str(e)}")
                )

        self.stdout.write(f"Loaded metadata for {len(all_documents)} documents")
        self.stdout.write(f"- CBT documents: {len(docs_by_therapy['cbt'])}")
        self.stdout.write(f"- DBT documents: {len(docs_by_therapy['dbt'])}")

        # Process large batches of text for more efficient GPU utilization
        # This works by collecting all chunks first, then batching the embedding generation
        all_chunks = []
        chunk_metadata = {}

        for doc_data in tqdm(all_documents, desc="Collecting chunks"):
            therapy = doc_data.get("therapy", "unknown")
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

            # Get chunks
            chunks = doc_data.get("chunks", [])

            # Apply chunk limit if specified
            if max_chunks is not None:
                remaining_slots = max_chunks - therapy_chunk_counts[therapy]
                if remaining_slots <= 0:
                    continue

                if len(chunks) > remaining_slots:
                    chunks = chunks[:remaining_slots]

            # Extract text for embedding
            for i, chunk in enumerate(chunks):
                text = chunk.get("text", "")
                if not text:
                    continue

                chunk_id = f"{doc_id}_chunk_{i}"
                all_chunks.append(text)
                chunk_metadata[len(all_chunks) - 1] = {
                    "id": chunk_id,
                    "document_id": doc_id,
                    "text": text,
                    "metadata": {
                        "page": chunk.get("page", 0),
                        "source": title,
                        "therapy_type": therapy,
                    },
                    "sequence": i,
                }

                document_index[doc_id]["chunk_count"] += 1
                therapy_chunk_counts[therapy] += 1
                total_chunks += 1

        # Report on collected chunks
        self.stdout.write(
            f"Collected {len(all_chunks)} total chunks for embedding generation"
        )
        self.stdout.write(
            f"CBT chunks: {therapy_chunk_counts['cbt']}, DBT chunks: {therapy_chunk_counts['dbt']}"
        )

        # Generate embeddings in optimized batches
        batch_results = []

        # Function to process a batch
        def process_batch(batch_idx, batch_texts):
            batch_start_time = time.time()
            result = []

            try:
                # Generate embeddings for the batch
                self.stdout.write(
                    f"Processing batch {batch_idx+1}/{len(range(0, len(all_chunks), batch_size))}: {len(batch_texts)} embeddings"
                )

                # Generate embeddings as efficiently as possible
                batch_embeddings = vector_store.generate_embeddings_batch(batch_texts)

                # Store each embedding with its metadata
                for i, embedding in enumerate(batch_embeddings):
                    original_idx = batch_idx * batch_size + i
                    if original_idx in chunk_metadata:
                        result.append((original_idx, embedding))

                batch_time = time.time() - batch_start_time
                self.stdout.write(
                    f"Batch {batch_idx+1} completed in {batch_time:.1f}s ({len(result)} embeddings)"
                )

                return result
            except Exception as e:
                self.stderr.write(f"Error processing batch {batch_idx}: {str(e)}")
                logger.error("Batch processing error", exc_info=True)
                return []

        # Process in batches with potential parallelism
        with tqdm(total=len(all_chunks), desc="Generating embeddings") as progress_bar:
            if parallel_workers > 1 and len(all_chunks) > batch_size * 2:
                # Use multiple workers for processing
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=parallel_workers
                ) as executor:
                    futures = []
                    for batch_idx, i in enumerate(
                        range(0, len(all_chunks), batch_size)
                    ):
                        batch_texts = all_chunks[i : i + batch_size]
                        futures.append(
                            executor.submit(process_batch, batch_idx, batch_texts)
                        )

                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        batch_results.extend(result)
                        progress_bar.update(len(result))
            else:
                # Process sequentially - better for smaller datasets or limited memory
                for batch_idx, i in enumerate(range(0, len(all_chunks), batch_size)):
                    batch_texts = all_chunks[i : i + batch_size]
                    result = process_batch(batch_idx, batch_texts)
                    batch_results.extend(result)
                    progress_bar.update(len(result))

        # Save chunks to files
        with tqdm(
            total=len(batch_results), desc="Saving chunks to files"
        ) as progress_bar:
            for original_idx, embedding in batch_results:
                metadata = chunk_metadata[original_idx]
                metadata["embedding"] = embedding

                therapy = metadata["metadata"]["therapy_type"]
                chunk_path = os.path.join(chunks_dir, therapy, f"{metadata['id']}.json")

                with open(chunk_path, "w") as f:
                    json.dump(metadata, f)

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
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        self.stdout.write(
            self.style.SUCCESS(
                f"Local vector store created successfully in {minutes}m {seconds}s!"
            )
        )
        self.stdout.write(f"CBT Documents: {therapy_counts['cbt']}")
        self.stdout.write(f"- Total chunks: {therapy_chunk_counts['cbt']}")
        self.stdout.write(f"DBT Documents: {therapy_counts['dbt']}")
        self.stdout.write(f"- Total chunks: {therapy_chunk_counts['dbt']}")
        self.stdout.write(f"Total documents: {total_docs}")
        self.stdout.write(f"Total chunks: {total_chunks}")
        self.stdout.write(f"\nLocal vector store created at: {chunks_dir}")

# chatbot/management/commands/setup_therapy_rag.py
import os
import json
import logging
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from tqdm import tqdm

# Fix imports to use community versions
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader

# Import GPU utils for acceleration check
from chatbot.services.rag.gpu_utils import verify_gpu_support

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up the RAG system for therapy content"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-dir",
            type=str,
            default=os.path.join(settings.BASE_DIR, "chatbot", "data"),
            help="Directory containing therapy content files",
        )
        parser.add_argument(
            "--chunk-size", type=int, default=1000, help="Size of text chunks for RAG"
        )
        parser.add_argument(
            "--chunk-overlap", type=int, default=200, help="Overlap between text chunks"
        )
        parser.add_argument(
            "--use-local",
            action="store_true",
            default=True,
            help="Use local file-based storage instead of database",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of the vector store if it exists",
        )

    def handle(self, *args, **options):
        try:
            start_time = time.time()
            source_dir = options["source_dir"]
            chunk_size = options["chunk_size"]
            chunk_overlap = options["chunk_overlap"]
            use_local = options["use_local"]
            force = options["force"]

            # Set up directories
            cbt_dir = os.path.join(source_dir, "cbt")
            dbt_dir = os.path.join(source_dir, "dbt")
            indexed_dir = os.path.join(source_dir, "indexed")
            chunks_dir = os.path.join(source_dir, "chunks")
            rag_data_dir = os.path.join(settings.BASE_DIR, "rag_data")

            # Create directories if they don't exist
            for directory in [
                cbt_dir,
                dbt_dir,
                indexed_dir,
                chunks_dir,
                os.path.join(chunks_dir, "index"),
                os.path.join(chunks_dir, "cbt"),
                os.path.join(chunks_dir, "dbt"),
                rag_data_dir,
            ]:
                os.makedirs(directory, exist_ok=True)

            self.stdout.write(
                self.style.SUCCESS(f"Starting therapy RAG setup from {source_dir}")
            )

            # Check GPU availability
            gpu_info = verify_gpu_support()
            if gpu_info and gpu_info.get("using_gpu"):
                self.stdout.write(
                    self.style.SUCCESS(f"🚀 GPU ENABLED: {gpu_info.get('details', '')}")
                )

                # Optimize GPU memory usage
                os.environ["OLLAMA_NUM_GPU"] = str(os.getenv("OLLAMA_NUM_GPU", "80"))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Set GPU layers to {os.environ['OLLAMA_NUM_GPU']} for maximum performance"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️ CPU ONLY MODE: No GPU detected or not properly configured"
                    )
                )

            # Check for PDF, DOCX, and TXT files
            cbt_files = [
                f
                for f in os.listdir(cbt_dir)
                if f.lower().endswith((".pdf", ".docx", ".txt"))
            ]
            dbt_files = [
                f
                for f in os.listdir(dbt_dir)
                if f.lower().endswith((".pdf", ".docx", ".txt"))
            ]

            if not cbt_files and not dbt_files:
                self.stdout.write(
                    self.style.ERROR(
                        "No PDF, DOCX, or TXT files found in the source directories."
                    )
                )
                self.stdout.write(f"Please add files to {cbt_dir} and {dbt_dir}")
                return

            self.stdout.write(
                f"Found {len(cbt_files)} CBT PDFs/DOCX/TXT and {len(dbt_files)} DBT PDFs/DOCX/TXT"
            )

            # Process CBT files
            documents = []

            if cbt_files:
                self.stdout.write(self.style.SUCCESS("\nProcessing CBT documents:"))
                for file_name in tqdm(cbt_files, desc="CBT Files"):
                    file_path = os.path.join(cbt_dir, file_name)
                    try:
                        # Loader selection based on file extension
                        if file_name.lower().endswith(".pdf"):
                            loader = PyPDFLoader(file_path)
                        elif file_name.lower().endswith(".docx"):
                            loader = Docx2txtLoader(file_path)
                        elif file_name.lower().endswith(".txt"):
                            loader = TextLoader(file_path)
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  ⚠️ Skipping unsupported file: {file_name}"
                                )
                            )
                            continue
                        docs = loader.load()
                        for doc in docs:
                            doc.metadata["therapy_type"] = "cbt"
                            doc.metadata["source"] = file_name
                            doc.metadata["title"] = f"CBT Document: {file_name}"
                        documents.extend(docs)
                        self.stdout.write(
                            f"  ✓ Processed {file_name} ({len(docs)} pages)"
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Error processing {file_name}: {str(e)}"
                            )
                        )

            # Process DBT files
            if dbt_files:
                self.stdout.write(self.style.SUCCESS("\nProcessing DBT documents:"))
                for file_name in tqdm(dbt_files, desc="DBT Files"):
                    file_path = os.path.join(dbt_dir, file_name)
                    try:
                        # Loader selection based on file extension
                        if file_name.lower().endswith(".pdf"):
                            loader = PyPDFLoader(file_path)
                        elif file_name.lower().endswith(".docx"):
                            loader = Docx2txtLoader(file_path)
                        elif file_name.lower().endswith(".txt"):
                            loader = TextLoader(file_path)
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  ⚠️ Skipping unsupported file: {file_name}"
                                )
                            )
                            continue
                        docs = loader.load()
                        for doc in docs:
                            doc.metadata["therapy_type"] = "dbt"
                            doc.metadata["source"] = file_name
                            doc.metadata["title"] = f"DBT Document: {file_name}"
                        documents.extend(docs)
                        self.stdout.write(
                            f"  ✓ Processed {file_name} ({len(docs)} pages)"
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Error processing {file_name}: {str(e)}"
                            )
                        )

            # Create text splitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )

            # Split documents into chunks
            self.stdout.write(f"\nSplitting {len(documents)} documents into chunks...")
            chunks = text_splitter.split_documents(documents)
            self.stdout.write(f"Created {len(chunks)} chunks")

            # Set up embeddings model
            self.stdout.write("\nGenerating embeddings...")
            embeddings = OllamaEmbeddings(
                model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest"),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            )

            # Progress bar for embedding generation
            def embed_documents_with_progress(chunks, embeddings):
                texts = [chunk.page_content for chunk in chunks]
                metadatas = [chunk.metadata for chunk in chunks]
                vectors = []
                for text in tqdm(texts, desc="Embedding chunks"):
                    vectors.append(embeddings.embed_query(text))
                return vectors, metadatas

            # Create vector store with progress bar
            db_path = os.path.join(rag_data_dir, "therapy_faiss")
            if os.path.exists(db_path) and not force:
                self.stdout.write(
                    f"Vector store already exists at {db_path}. Use --force to recreate."
                )
                vectorstore = FAISS.load_local(db_path, embeddings)
            else:
                self.stdout.write(f"Creating new vector store at {db_path}...")
                # Generate embeddings with progress bar
                vectors, metadatas = embed_documents_with_progress(chunks, embeddings)
                from langchain_community.vectorstores.faiss import (
                    dependable_faiss_import,
                )

                faiss = dependable_faiss_import()
                import numpy as np

                index = faiss.IndexFlatL2(len(vectors[0]))
                index.add(np.array(vectors).astype("float32"))
                vectorstore = FAISS(
                    embedding_function=embeddings,
                    index=index,
                    docstore=None,
                    index_to_docstore_id=None,
                )
                vectorstore.save_local(db_path)

            # Create config file
            config = {
                "version": "1.0",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "chunk_count": len(chunks),
                "document_count": len(documents),
                "therapy_counts": {
                    "cbt": len(cbt_files),
                    "dbt": len(dbt_files),
                },
                "embedding_model": os.getenv(
                    "EMBEDDING_MODEL", "nomic-embed-text:latest"
                ),
                "embedding_dimension": 384,
                "gpu_enabled": bool(gpu_info and gpu_info.get("using_gpu", False)),
            }

            with open(os.path.join(chunks_dir, "config.json"), "w") as f:
                json.dump(config, f, indent=2)

            # Write therapy indexes
            cbt_chunks = [
                i
                for i, chunk in enumerate(chunks)
                if chunk.metadata.get("therapy_type") == "cbt"
            ]
            dbt_chunks = [
                i
                for i, chunk in enumerate(chunks)
                if chunk.metadata.get("therapy_type") == "dbt"
            ]

            with open(os.path.join(chunks_dir, "index", "documents.json"), "w") as f:
                json.dump(
                    {
                        "cbt_1": {
                            "id": "cbt_1",
                            "therapy_type": "cbt",
                            "title": "Cognitive Behavioral Therapy Documents",
                            "chunk_count": len(cbt_chunks),
                        },
                        "dbt_1": {
                            "id": "dbt_1",
                            "therapy_type": "dbt",
                            "title": "Dialectical Behavior Therapy Documents",
                            "chunk_count": len(dbt_chunks),
                        },
                    },
                    f,
                    indent=2,
                )

            with open(os.path.join(chunks_dir, "index", "cbt_chunks.json"), "w") as f:
                json.dump(cbt_chunks, f)

            with open(os.path.join(chunks_dir, "index", "dbt_chunks.json"), "w") as f:
                json.dump(dbt_chunks, f)

            # Test the system
            self.stdout.write("\nTesting RAG system...")
            llm = Ollama(
                model=os.getenv("LLM_MODEL", "mistral"),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                temperature=0.2,
            )

            from langchain.chains import RetrievalQA

            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
                return_source_documents=True,
            )

            test_query = "What are some common CBT techniques for anxiety and how are they applied?"
            self.stdout.write(f"Test query: {test_query}")

            try:
                result = qa_chain({"query": test_query})
                self.stdout.write(f"Response: {result['result'][:200]}...")
                self.stdout.write(
                    f"Sources: {[doc.metadata.get('source', 'Unknown') for doc in result['source_documents']]}"
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Test query failed: {str(e)}"))

            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nTherapy RAG setup completed in {minutes}m {seconds}s"
                )
            )
            self.stdout.write(
                f"Created {len(chunks)} chunks from {len(documents)} documents"
            )
            self.stdout.write(f"Vector store saved to {db_path}")

        except Exception as e:
            logger.error(
                f"Error setting up therapy RAG system: {str(e)}", exc_info=True
            )
            self.stderr.write(
                self.style.ERROR(f"Error in setup_therapy_rag command: {str(e)}")
            )

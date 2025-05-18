# chatbot/management/commands/pull_embedding_model.py
import os
import requests
import logging
import time
from django.core.management.base import BaseCommand
from tqdm import tqdm

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Pull the embedding model for RAG system with progress tracking"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help="Specify the embedding model to pull (default: from .env)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Timeout in seconds for the pull operation (default: 300)",
        )

    def handle(self, *args, **options):
        model = options["model"] or os.getenv(
            "EMBEDDING_MODEL", "nomic-embed-text:latest"
        )
        timeout = options["timeout"]

        self.stdout.write(self.style.NOTICE(f"Pulling embedding model: {model}"))
        self.stdout.write(
            "This may take several minutes for large models like mxbai-embed-large..."
        )

        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        try:
            # Start the pull with stream=true to get progress updates
            response = requests.post(
                f"{ollama_host}/api/pull",
                json={"name": model, "stream": True},
                stream=True,
                timeout=5,  # Initial connection timeout
            )

            # Check if the request was accepted
            if response.status_code != 200:
                self.stderr.write(
                    self.style.ERROR(f"Failed to start model pull: {response.text}")
                )
                return

            # Setup progress tracking
            start_time = time.time()
            last_progress = 0
            progress_bar = tqdm(total=100, desc="Downloading model", ncols=100)

            # Process the streaming response
            for line in response.iter_lines():
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    progress_bar.close()
                    raise TimeoutError(f"Pull operation exceeded {timeout} seconds")

                if line:
                    try:
                        data = line.decode("utf-8")
                        # Handle Ollama's streaming JSON format
                        if "progress" in data:
                            import json

                            progress_data = json.loads(data)
                            if "completed" in progress_data:
                                progress = min(
                                    int(float(progress_data["completed"]) * 100), 100
                                )
                                progress_bar.update(progress - last_progress)
                                last_progress = progress
                    except Exception as e:
                        # Log the exception for debugging purposes
                        logger.warning(f"Error parsing progress data: {e}")
                        pass

            progress_bar.close()

            # Verify the model is now available
            self.stdout.write("Verifying model availability...")
            verify_response = requests.post(
                f"{ollama_host}/api/embeddings",
                json={"model": model, "prompt": "Test embedding"},
                timeout=30,
            )

            if verify_response.status_code == 200:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully pulled embedding model: {model}")
                )
                embedding_dim = len(verify_response.json()["embedding"])
                self.stdout.write(f"Model embedding dimension: {embedding_dim}")
                self.stdout.write(
                    f"Make sure your EMBEDDING_DIMENSION in .env is set to {embedding_dim}"
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        "Model pull may have failed. Verification unsuccessful."
                    )
                )

        except TimeoutError as e:
            self.stderr.write(self.style.ERROR(str(e)))
        except requests.exceptions.ConnectionError:
            self.stderr.write(
                self.style.ERROR(
                    f"Connection error: Ollama server not running at {ollama_host}"
                )
            )
        except requests.exceptions.Timeout:
            self.stderr.write(
                self.style.ERROR("Connection timed out. Is Ollama running?")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error pulling model: {str(e)}"))

# AI_engine/management/commands/initialize_ai.py
import requests
import json
import sys
import time
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initialize AI models and verify setup"

    def handle(self, *args, **kwargs):
        """Initialize both Ollama and Gemini integrations"""
        self.stdout.write("Initializing AI engine...")
        success = True

        # Check Gemini API key
        if not settings.GEMINI_API_KEY:
            self.stderr.write(
                self.style.ERROR(
                    "Gemini API key not found. Please set GEMINI_API_KEY in your environment."
                )
            )
            success = False
        else:
            self.stdout.write(self.style.SUCCESS("✓ Gemini API key configured"))

        # Check Ollama connection
        try:
            response = requests.get(f"{settings.OLLAMA_URL}/api/tags")
            if response.status_code != 200:
                self.stderr.write(
                    self.style.ERROR(
                        "Ollama API is not responding. Please ensure Ollama is running."
                    )
                )
                success = False
            else:
                self.stdout.write(
                    self.style.SUCCESS("✓ Ollama API connection successful")
                )
        except requests.exceptions.ConnectionError:
            self.stderr.write(
                self.style.ERROR(
                    "Could not connect to Ollama API. Please ensure Ollama is installed and running."
                )
            )
            success = False
            return

        # Required Ollama model
        model = "mistral"
        try:
            # Check if model exists
            model_check = requests.get(
                f"{settings.OLLAMA_URL}/api/show", params={"name": model}
            )

            if model_check.status_code == 404:
                self.stdout.write(f"Downloading {model} model...")

                # Start model pull with streaming
                with requests.post(
                    f"{settings.OLLAMA_URL}/api/pull", json={"name": model}, stream=True
                ) as response:
                    if response.status_code == 200:
                        total_size = 0
                        start_time = time.time()
                        current_status = ""

                        for line in response.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line)
                                    status = data.get("status", "")

                                    # Update download progress
                                    if "completed" in data:
                                        completed = data["completed"]
                                        total = data.get("total", 0)
                                        if total > 0:
                                            progress = (completed / total) * 100
                                            elapsed_time = time.time() - start_time
                                            download_speed = (
                                                completed / (1024 * 1024 * elapsed_time)
                                                if elapsed_time > 0
                                                else 0
                                            )

                                            status_line = f"\rProgress: {progress:.1f}% - Downloaded: {completed/(1024*1024):.1f}MB - Speed: {download_speed:.1f}MB/s"
                                            if status and status != current_status:
                                                status_line += f" - Status: {status}"
                                                current_status = status

                                            sys.stdout.write(status_line)
                                            sys.stdout.flush()
                                            total_size = completed

                                except json.JSONDecodeError:
                                    continue

                        sys.stdout.write("\n")
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Successfully downloaded {model} "
                                f"(Total size: {total_size/(1024*1024):.1f}MB, "
                                f"Time: {time.time()-start_time:.1f}s)"
                            )
                        )
                    else:
                        self.stderr.write(
                            self.style.ERROR(f"Failed to download {model}")
                        )
                        success = False
            else:
                self.stdout.write(self.style.SUCCESS(f"✓ Model {model} is ready"))

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error processing {model} model: {str(e)}")
            )
            success = False

        if success:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ AI engine initialization completed successfully"
                )
            )
        else:
            self.stderr.write(
                self.style.ERROR("\n⨯ AI engine initialization completed with errors")
            )

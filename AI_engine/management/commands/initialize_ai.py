import requests
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Initialize AI models and verify setup'

    def handle(self, *args, **kwargs):
        """Initialize both Ollama and Gemini integrations"""
        self.stdout.write("Initializing AI engine...")
        success = True
        
        # Check Gemini API key
        if not settings.GEMINI_API_KEY:
            self.stderr.write(
                self.style.ERROR("Gemini API key not found. Please set GEMINI_API_KEY in your environment.")
            )
            success = False
        else:
            self.stdout.write(self.style.SUCCESS("✓ Gemini API key configured"))

        # Check Ollama connection
        try:
            response = requests.get(f"{settings.OLLAMA_URL}/api/tags")
            if response.status_code != 200:
                self.stderr.write(
                    self.style.ERROR("Ollama API is not responding. Please ensure Ollama is running.")
                )
                success = False
            else:
                self.stdout.write(self.style.SUCCESS("✓ Ollama API connection successful"))
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
                f"{settings.OLLAMA_URL}/api/show",
                params={"name": model}
            )
            
            if model_check.status_code == 404:
                self.stdout.write(f"Downloading {model} model...")
                pull_response = requests.post(
                    f"{settings.OLLAMA_URL}/api/pull",
                    json={"name": model}
                )
                if pull_response.status_code == 200:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Successfully downloaded {model}")
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
            self.stdout.write(self.style.SUCCESS("\n✓ AI engine initialization completed successfully"))
        else:
            self.stderr.write(
                self.style.ERROR("\n⨯ AI engine initialization completed with errors")
            )
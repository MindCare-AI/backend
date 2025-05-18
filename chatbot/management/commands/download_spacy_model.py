# chatbot/management/commands/download_spacy_model.py
import subprocess
import sys
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Download SpaCy model required for sentence tokenization in RAG"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default="en_core_web_sm",
            help="SpaCy model name (default: en_core_web_sm)",
        )

    def handle(self, *args, **options):
        model_name = options.get("model", "en_core_web_sm")

        self.stdout.write(f"Downloading SpaCy model: {model_name}")

        try:
            # First check if the model is already installed
            try:
                import spacy

                spacy.load(model_name)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"SpaCy model '{model_name}' is already installed"
                    )
                )
                return
            except IOError:
                self.stdout.write(
                    f"SpaCy model '{model_name}' not found. Downloading..."
                )

            # Install the model
            subprocess.check_call(
                [sys.executable, "-m", "spacy", "download", model_name]
            )

            # Verify installation
            import spacy

            spacy.load(model_name)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully downloaded and installed SpaCy model '{model_name}'"
                )
            )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error downloading SpaCy model: {str(e)}")
            )
            self.stderr.write(
                self.style.WARNING(
                    "Try installing manually: python -m spacy download en_core_web_sm"
                )
            )
            logger.error(f"Error downloading SpaCy model: {str(e)}")

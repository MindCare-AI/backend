#messaging/management/commands/setup_ollama_model.py
import subprocess
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify and download the Ollama model if necessary"

    def handle(self, *args, **kwargs):
        model_name = "samantha-mistral"  # Model name configuration

        try:
            # Check if Ollama is installed
            self._check_ollama_installation()

            # Check if model exists
            if self._check_model_exists(model_name):
                self.stdout.write(
                    self.style.SUCCESS(f'Model "{model_name}" is already downloaded.')
                )
                return

            # Download the model
            self._download_model(model_name)

        except OllamaNotFoundError:
            self.stderr.write(
                self.style.ERROR("Ollama is not installed or not found in PATH.")
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(
                self.style.ERROR(
                    f'Command failed: {e.stderr if hasattr(e, "stderr") else str(e)}'
                )
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Unexpected error: {str(e)}"))

    def _check_ollama_installation(self):
        """Verify Ollama is installed and accessible"""
        try:
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
        except FileNotFoundError:
            raise OllamaNotFoundError()

    def _check_model_exists(self, model_name):
        """Check if the specified model is already downloaded"""
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        )
        return model_name in result.stdout

    def _download_model(self, model_name):
        """Download the specified model"""
        self.stdout.write(f'Model "{model_name}" not found. Downloading...')
        process = subprocess.run(
            ["ollama", "pull", model_name], capture_output=True, text=True, check=True
        )
        self.stdout.write(
            self.style.SUCCESS(f'Model "{model_name}" downloaded successfully.')
        )


class OllamaNotFoundError(Exception):
    pass

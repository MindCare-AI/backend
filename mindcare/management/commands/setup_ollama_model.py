# myapp/management/commands/setup_ollama_model.py
import subprocess
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify and download the Ollama model if necessary"

    def handle(self, *args, **kwargs):
        model_name = "llama2"  # Replace with your desired model name
        try:
            # Check if the model is already downloaded
            result = subprocess.run(["ollama", "ls"], capture_output=True, text=True)
            if model_name in result.stdout:
                self.stdout.write(
                    self.style.SUCCESS(f'Model "{model_name}" is already downloaded.')
                )
            else:
                self.stdout.write(f'Model "{model_name}" not found. Downloading...')
                subprocess.run(["ollama", "pull", model_name], check=True)
                self.stdout.write(
                    self.style.SUCCESS(f'Model "{model_name}" downloaded successfully.')
                )
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"An error occurred: {e}"))
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR("Ollama is not installed or not found in PATH.")
            )

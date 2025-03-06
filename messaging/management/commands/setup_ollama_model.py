import subprocess
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify and download the Ollama model with GPU support if available"

    def handle(self, *args, **kwargs):
        model_name = "samantha-mistral"  # Model name configuration

        try:
            # Check if Ollama is installed
            self._check_ollama_installation()

            # Check GPU availability
            gpu_available = self._check_gpu_available()
            if gpu_available:
                self.stdout.write(
                    self.style.SUCCESS("GPU detected and available for Ollama")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("No GPU detected, Ollama will run on CPU only")
                )

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
            self._provide_installation_instructions()
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

    def _check_gpu_available(self):
        """Check if NVIDIA GPU is available for Ollama"""
        try:
            # Check for nvidia-smi
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Check for device nodes
        if os.path.exists("/dev/nvidia0"):
            return True

        return False

    def _check_model_exists(self, model_name):
        """Check if the specified model is already downloaded"""
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        )
        return model_name in result.stdout

    def _download_model(self, model_name):
        """Download the specified model"""
        self.stdout.write(f'Model "{model_name}" not found. Downloading...')
        subprocess.run(
            ["ollama", "pull", model_name], capture_output=True, text=True, check=True
        )
        self.stdout.write(
            self.style.SUCCESS(f'Model "{model_name}" downloaded successfully.')
        )

    def _provide_installation_instructions(self):
        """Provide instructions for installing Ollama with GPU support"""
        self.stdout.write(self.style.WARNING("\nOllama Installation Instructions:"))
        self.stdout.write(
            "1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh"
        )
        self.stdout.write(
            "2. For GPU support, ensure NVIDIA drivers and CUDA are installed"
        )
        self.stdout.write("   - For Ubuntu: sudo apt install nvidia-driver-XXX cuda")
        self.stdout.write("3. Run 'ollama serve' in a separate terminal")
        self.stdout.write("4. Run this command again to download the model\n")


class OllamaNotFoundError(Exception):
    pass

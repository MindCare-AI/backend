import subprocess
import requests
import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check Ollama status, GPU usage, and perform a quick benchmark"

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking Ollama and GPU status...")
        
        # Check if Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS("✓ Ollama server is running"))
            else:
                self.stdout.write(self.style.ERROR("✗ Ollama server returned unexpected response"))
                return
        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR("✗ Ollama server is not running"))
            self.stdout.write("  Start Ollama with: ollama serve")
            return
            
        # Check available models
        try:
            response = requests.get("http://localhost:11434/api/tags")
            models = response.json().get("models", [])
            
            if models:
                self.stdout.write(self.style.SUCCESS(f"✓ Available models: {', '.join([m['name'] for m in models])}"))
            else:
                self.stdout.write(self.style.WARNING("No models found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking models: {str(e)}"))
            
        # Check GPU status
        try:
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("✓ NVIDIA GPU detected"))
                # Extract some useful info
                for line in result.stdout.split("\n"):
                    if "CUDA Version" in line:
                        self.stdout.write(f"  {line.strip()}")
            else:
                self.stdout.write(self.style.WARNING("✗ NVIDIA GPU not detected or accessible"))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING("✗ nvidia-smi not found, GPU may not be available"))
            
        # Run a quick benchmark
        self.stdout.write("\nRunning quick benchmark...")
        try:
            model = "samantha-mistral"
            prompt = "How can I manage anxiety during stressful situations?"
            
            start_time = time.time()
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                }
            )
            
            if response.status_code == 200:
                end_time = time.time()
                elapsed = end_time - start_time
                result = response.json()
                tokens = result.get("eval_count", 0)
                
                self.stdout.write(self.style.SUCCESS(f"✓ Benchmark complete"))
                self.stdout.write(f"  Response time: {elapsed:.2f} seconds")
                self.stdout.write(f"  Tokens generated: {tokens}")
                self.stdout.write(f"  Speed: {tokens/elapsed:.2f} tokens/sec")
            else:
                self.stdout.write(self.style.ERROR("✗ Benchmark failed"))
                self.stdout.write(f"  Error: {response.text}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Benchmark error: {str(e)}"))
import subprocess

def verify_gpu_support():
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True
        )
        if "failed" in result.stdout.lower():
            raise RuntimeError("NVIDIA drivers not properly installed")
        return True
    except FileNotFoundError:
        raise RuntimeError("NVIDIA-SMI not found - GPU unavailable")

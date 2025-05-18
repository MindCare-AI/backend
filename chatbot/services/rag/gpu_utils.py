# chatbot/services/rag/gpu_utils.py
import subprocess
import logging
import os
import re
import platform
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def verify_gpu_support() -> Dict[str, Any]:
    """Check if GPU is available and properly configured for use with Ollama.

    Returns:
        Dictionary with detailed GPU information and status
    """
    default_gpu_layers = int(
        os.getenv("OLLAMA_DEFAULT_NUM_GPU", 25)
    )  # Configurable default

    # Initialize result with default values
    result = {
        "using_gpu": False,
        "details": "CPU only mode",
        "device_info": None,
        "gpu_model": None,
        "gpu_memory": None,
        "cuda_version": None,
        "gpu_utilization": None,
    }

    try:
        # Log GPU layers being used
        gpu_layers = os.getenv("OLLAMA_NUM_GPU", "0")
        logger.info(f"OLLAMA_NUM_GPU is set to {gpu_layers}")

        # First check if Ollama reports GPU usage via API
        gpu_info = _check_ollama_gpu_usage()
        if gpu_info and gpu_info.get("using_gpu"):
            result.update(gpu_info)
            logger.info(f"Ollama reports GPU usage: {gpu_info}")
            return result

        # If Ollama API didn't confirm GPU, check using NVIDIA tools
        nvidia_info = _check_nvidia_gpu()
        if nvidia_info and nvidia_info.get("using_gpu"):
            result.update(nvidia_info)
            # Set appropriate GPU layers based on available memory
            _set_gpu_layers_from_memory(nvidia_info.get("gpu_memory_mb", 0))
            logger.info(f"NVIDIA GPU detected: {nvidia_info}")
            return result

        # If no GPU via NVIDIA tools, check for other GPU types (AMD, Intel)
        other_gpu = _check_other_gpus()
        if other_gpu and other_gpu.get("using_gpu"):
            result.update(other_gpu)
            logger.info(f"Other GPU detected: {other_gpu}")
            return result

        # No GPU detected
        os.environ["OLLAMA_NUM_GPU"] = "0"  # Disable GPU layers
        logger.warning("No compatible GPU detected, using CPU only")
        return result

    except Exception as e:
        logger.exception(f"Error checking GPU support: {str(e)}")
        os.environ["OLLAMA_NUM_GPU"] = str(default_gpu_layers)
        result["details"] = f"Error checking GPU: {str(e)}"
        return result

    if result["using_gpu"]:
        logger.info(f"GPU detected and being used: {result['details']}")
    else:
        logger.warning("No GPU detected, falling back to CPU.")
    return result


def _check_ollama_gpu_usage() -> Optional[Dict[str, Any]]:
    """
    Check if Ollama API reports GPU usage.
    """
    try:
        # Example: Replace with actual Ollama API endpoint if available
        response = requests.get("http://localhost:11434/api/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            device_info = data.get("device", {})
            model_name = data.get("model", "unknown")
            gpu_enabled = bool(device_info.get("parameters", {}).get("gpu"))

            if gpu_enabled:
                return {
                    "using_gpu": True,
                    "details": f"Ollama using GPU for {model_name}",
                    "device_info": device_info,
                    "gpu_model": device_info.get("model", "Unknown GPU"),
                }
    except Exception as e:
        logger.debug(f"Error checking Ollama GPU usage: {str(e)}")

    return None


def _check_nvidia_gpu() -> Optional[Dict[str, Any]]:
    """Check for NVIDIA GPU using nvidia-smi"""
    try:
        # Check if nvidia-smi is available
        nvidia_smi = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.free,memory.total,driver_version,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output: name, free memory, total memory, driver version, GPU utilization
        output = nvidia_smi.stdout.strip().split(",")
        if len(output) >= 3:
            gpu_name = output[0].strip()
            free_memory = int(output[1].strip())
            total_memory = int(output[2].strip())
            driver_version = output[3].strip() if len(output) > 3 else "Unknown"
            gpu_utilization = output[4].strip() if len(output) > 4 else "Unknown"

            # Get CUDA version
            cuda_version = _get_cuda_version()

            # Check if Ollama process is using GPU
            ollama_using_gpu = _check_ollama_process_gpu_usage()

            result = {
                "using_gpu": True,
                "details": f"{gpu_name} ({free_memory}/{total_memory} MB free)",
                "gpu_model": gpu_name,
                "gpu_memory": f"{free_memory}/{total_memory} MB free",
                "gpu_memory_mb": free_memory,
                "cuda_version": cuda_version,
                "gpu_utilization": gpu_utilization,
                "driver_version": driver_version,
                "ollama_using_gpu": ollama_using_gpu,
            }

            return result

    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.debug(f"NVIDIA GPU check failed: {str(e)}")

    return None


def _check_ollama_process_gpu_usage() -> bool:
    """Check if Ollama process is using GPU resources"""
    try:
        # Get list of GPU processes
        gpu_procs = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,name,used_memory",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
        )

        # Check if ollama process is in the list
        for line in gpu_procs.stdout.splitlines():
            if "ollama" in line.lower():
                return True

        # If not, check if Ollama is running but not listed in GPU processes
        ps_check = subprocess.run(["ps", "-aux"], capture_output=True, text=True)

        ollama_running = any("ollama" in line for line in ps_check.stdout.splitlines())
        if ollama_running:
            logger.warning("Ollama process is running but not using GPU")

        return False

    except Exception:
        return False


def _check_other_gpus() -> Optional[Dict[str, Any]]:
    """Check for non-NVIDIA GPUs (AMD, Intel)"""
    result = None

    # Check for AMD GPUs
    if platform.system() == "Linux":
        try:
            # Check for AMD GPU on Linux
            if os.path.exists("/sys/class/drm/card0/device/vendor"):
                with open("/sys/class/drm/card0/device/vendor", "r") as f:
                    vendor_id = f.read().strip()
                    if vendor_id == "0x1002":  # AMD vendor ID
                        # Try to get GPU model
                        model = "AMD GPU"
                        try:
                            with open("/sys/class/drm/card0/device/product", "r") as f:
                                model = f"AMD {f.read().strip()}"
                        except Exception as e:
                            logger.debug(f"Error reading AMD GPU model: {str(e)}")

                        result = {
                            "using_gpu": True,
                            "details": f"{model} (ROCm support unknown)",
                            "gpu_model": model,
                            "gpu_memory": "Unknown",
                        }
        except Exception as e:
            logger.debug(f"Error checking AMD GPU: {str(e)}")

    # Check for Intel GPUs
    if not result and platform.system() == "Linux":
        try:
            lspci = subprocess.run(["lspci"], capture_output=True, text=True)

            intel_pattern = re.compile(r"VGA.*Intel", re.IGNORECASE)
            if any(intel_pattern.search(line) for line in lspci.stdout.splitlines()):
                result = {
                    "using_gpu": True,
                    "details": "Intel integrated GPU (limited acceleration)",
                    "gpu_model": "Intel integrated graphics",
                    "gpu_memory": "Shared memory",
                }
        except Exception as e:
            logger.debug(f"Error checking Intel GPU: {str(e)}")

    return result


def _get_cuda_version() -> Optional[str]:
    """Get CUDA version if available"""
    try:
        # First try nvcc
        nvcc = subprocess.run(["nvcc", "--version"], capture_output=True, text=True)
        match = re.search(r"release (\d+\.\d+)", nvcc.stdout)
        if match:
            return match.group(1)

        # Try nvidia-smi
        smi = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        match = re.search(r"CUDA Version: (\d+\.\d+)", smi.stdout)
        if match:
            return match.group(1)
    except Exception:
        pass

    return None


def _set_gpu_layers_from_memory(free_memory_mb: int) -> None:
    """Set appropriate GPU layers based on available memory."""
    if free_memory_mb <= 0:
        # Default to 0 if memory info not available
        os.environ["OLLAMA_NUM_GPU"] = "0"
        return

    # Scale GPU layers based on available memory
    if free_memory_mb > 8000:
        os.environ["OLLAMA_NUM_GPU"] = "99"  # Maximum GPU usage
        logger.info("Set maximum GPU layers (99) due to high available memory")
    elif free_memory_mb > 6000:
        os.environ["OLLAMA_NUM_GPU"] = "75"
        logger.info("Set high GPU layers (75) for available memory")
    elif free_memory_mb > 4000:
        os.environ["OLLAMA_NUM_GPU"] = "50"
        logger.info("Set medium GPU layers (50) for available memory")
    elif free_memory_mb > 2000:
        os.environ["OLLAMA_NUM_GPU"] = "35"
        logger.info("Set lower GPU layers (35) for limited memory")
    elif free_memory_mb > 1000:
        os.environ["OLLAMA_NUM_GPU"] = "20"
        logger.info("Set minimal GPU layers (20) for very limited memory")
    else:
        os.environ["OLLAMA_NUM_GPU"] = "0"  # Disable GPU for very low memory
        logger.warning("Disabled GPU layers due to insufficient memory")


def get_gpu_status_display() -> Dict[str, Any]:
    """Get GPU status with formatted display strings for the UI"""
    gpu_info = verify_gpu_support()

    result = {
        "using_gpu": gpu_info.get("using_gpu", False),
        "emoji": "🚀" if gpu_info.get("using_gpu") else "💻",
        "status": "ENABLED" if gpu_info.get("using_gpu") else "DISABLED",
        "details": gpu_info.get("details", "CPU only mode"),
        "color": "green" if gpu_info.get("using_gpu") else "yellow",
    }

    # Add benchmark info if available
    if gpu_info.get("using_gpu"):
        # Enhance display with more detailed information
        gpu_model = gpu_info.get("gpu_model", "Unknown GPU")
        gpu_memory = gpu_info.get("gpu_memory", "")
        cuda_version = gpu_info.get("cuda_version", "")

        # Format details string
        details_parts = []
        if gpu_model:
            details_parts.append(gpu_model)
        if gpu_memory:
            details_parts.append(f"Memory: {gpu_memory}")
        if cuda_version:
            details_parts.append(f"CUDA {cuda_version}")

        result["details"] = " | ".join(details_parts)
        result["full_info"] = gpu_info

        # Add number of GPU layers being used
        result["gpu_layers"] = os.environ.get("OLLAMA_NUM_GPU", "unknown")

    return result

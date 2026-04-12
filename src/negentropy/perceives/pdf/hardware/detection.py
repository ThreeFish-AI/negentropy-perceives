"""Hardware detection module for GPU acceleration support.

This module provides hardware detection capabilities to identify the optimal
computing device (MPS for Apple Silicon, CUDA for NVIDIA, XPU for Intel, or CPU)
for Docling and other ML-based processing tasks.

Design Pattern: Strategy Pattern - device detection and selection strategy
Reference: PyTorch device management best practices

Supported Devices:
    - MPS: Apple Silicon M-series chips (M1/M2/M3/M4)
    - CUDA: NVIDIA GPUs with CUDA support
    - XPU: Intel GPUs (Arc, integrated)
    - CPU: Fallback for all other platforms
"""

import logging
import platform
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Enumeration of supported compute devices for GPU acceleration.

    Values align with PyTorch device strings and Docling AcceleratorDevice.

    References:
        - PyTorch Device Documentation: https://pytorch.org/docs/stable/tensor_attributes.html#torch.device
        - Docling AcceleratorDevice: https://github.com/docling-project/docling
    """

    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"  # NVIDIA GPU
    MPS = "mps"  # Apple Silicon Metal Performance Shaders
    XPU = "xpu"  # Intel oneAPI

    @property
    def is_gpu(self) -> bool:
        """Check if this device type represents a GPU accelerator."""
        return self in (DeviceType.CUDA, DeviceType.MPS, DeviceType.XPU)


class HardwareInfo:
    """Container for detected hardware information."""

    def __init__(
        self,
        device_type: DeviceType,
        device_name: Optional[str] = None,
        device_count: int = 0,
        memory_gb: Optional[float] = None,
        platform_info: Optional[str] = None,
    ):
        self.device_type = device_type
        self.device_name = device_name
        self.device_count = device_count
        self.memory_gb = memory_gb
        self.platform_info = (
            platform_info or f"{platform.system()} {platform.machine()}"
        )

    def __repr__(self) -> str:
        details = []
        if self.device_name:
            details.append(f"name={self.device_name}")
        if self.device_count > 0:
            details.append(f"count={self.device_count}")
        if self.memory_gb:
            details.append(f"memory={self.memory_gb:.1f}GB")
        detail_str = ", ".join(details) if details else "N/A"
        return f"HardwareInfo(device={self.device_type.value}, {detail_str})"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "device_type": self.device_type.value,
            "device_name": self.device_name,
            "device_count": self.device_count,
            "memory_gb": self.memory_gb,
            "platform_info": self.platform_info,
            "is_gpu": self.device_type.is_gpu,
        }


def _check_mps_available() -> Tuple[bool, Optional[str], Optional[float]]:
    """Check if Apple Silicon MPS is available.

    Returns:
        Tuple of (is_available, device_name, memory_gb)
    """
    try:
        import torch

        if not hasattr(torch.backends, "mps"):
            return False, None, None

        if not torch.backends.mps.is_built():
            logger.debug("MPS backend is not built")
            return False, None, None

        if not torch.backends.mps.is_available():
            logger.debug("MPS device is not available")
            return False, None, None

        # MPS is available
        # Note: MPS doesn't expose direct memory info, use system memory as approximation
        try:
            import subprocess  # nosec B404

            result = subprocess.run(  # nosec B607 B603
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                total_memory = int(result.stdout.strip()) / (1024**3)  # Convert to GB
                # Estimate GPU can use ~75% of unified memory
                memory_gb = total_memory * 0.75
            else:
                memory_gb = None
        except Exception:
            memory_gb = None

        # Get chip name
        chip_name = None
        try:
            result = subprocess.run(  # nosec B607 B603
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                chip_name = result.stdout.strip()
        except Exception:
            chip_name = "Apple Silicon"

        return True, chip_name, memory_gb

    except ImportError:
        logger.debug("PyTorch not installed, cannot check MPS")
        return False, None, None
    except Exception as e:
        logger.warning(f"Error checking MPS availability: {e}")
        return False, None, None


def _check_cuda_available() -> Tuple[bool, Optional[str], int, Optional[float]]:
    """Check if NVIDIA CUDA is available.

    Returns:
        Tuple of (is_available, device_name, device_count, total_memory_gb)
    """
    try:
        import torch

        if not torch.cuda.is_available():
            logger.debug("CUDA is not available")
            return False, None, 0, None

        device_count = torch.cuda.device_count()
        if device_count == 0:
            return False, None, 0, None

        # Get primary device info
        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / (
            1024**3
        )  # Convert to GB

        return True, device_name, device_count, total_memory

    except ImportError:
        logger.debug("PyTorch not installed, cannot check CUDA")
        return False, None, 0, None
    except Exception as e:
        logger.warning(f"Error checking CUDA availability: {e}")
        return False, None, 0, None


def _check_xpu_available() -> Tuple[bool, Optional[str], int, Optional[float]]:
    """Check if Intel XPU is available.

    Returns:
        Tuple of (is_available, device_name, device_count, total_memory_gb)
    """
    try:
        import torch

        if not hasattr(torch, "xpu"):
            return False, None, 0, None

        if not torch.xpu.is_available():
            logger.debug("XPU is not available")
            return False, None, 0, None

        device_count = torch.xpu.device_count()
        if device_count == 0:
            return False, None, 0, None

        # Get primary device info
        device_name = torch.xpu.get_device_name(0)
        try:
            # XPU memory API may vary
            memory_info = torch.xpu.get_device_properties(0)
            total_memory = getattr(memory_info, "total_memory", None)
            if total_memory:
                total_memory = total_memory / (1024**3)  # Convert to GB
        except Exception:
            total_memory = None

        return True, device_name, device_count, total_memory

    except ImportError:
        logger.debug("PyTorch not installed, cannot check XPU")
        return False, None, 0, None
    except Exception as e:
        logger.warning(f"Error checking XPU availability: {e}")
        return False, None, 0, None


def detect_device() -> DeviceType:
    """Automatically detect the best available compute device.

    Detection priority (from highest to lowest performance for ML tasks):
        1. CUDA (NVIDIA GPU) - Best for large-scale ML inference
        2. MPS (Apple Silicon) - Excellent for M-series chips
        3. XPU (Intel GPU) - Good for Intel Arc GPUs
        4. CPU - Universal fallback

    Returns:
        DeviceType: The detected optimal device type

    Example:
        >>> device = detect_device()
        >>> print(f"Using {device.value} for acceleration")
        Using mps for acceleration
    """
    # Check CUDA first (typically highest performance)
    is_cuda, _, _, _ = _check_cuda_available()
    if is_cuda:
        logger.info("CUDA (NVIDIA GPU) detected")
        return DeviceType.CUDA

    # Check MPS (Apple Silicon)
    is_mps, _, _ = _check_mps_available()
    if is_mps:
        logger.info("MPS (Apple Silicon) detected")
        return DeviceType.MPS

    # Check XPU (Intel)
    is_xpu, _, _, _ = _check_xpu_available()
    if is_xpu:
        logger.info("XPU (Intel GPU) detected")
        return DeviceType.XPU

    # Fallback to CPU
    logger.info("No GPU detected, using CPU")
    return DeviceType.CPU


def get_hardware_info() -> HardwareInfo:
    """Get detailed information about the detected hardware.

    Returns:
        HardwareInfo: Object containing device type, name, count, and memory info

    Example:
        >>> info = get_hardware_info()
        >>> print(info)
        HardwareInfo(device=mps, name=Apple M2 Pro, memory=24.0GB)
    """
    platform_info = f"{platform.system()} {platform.release()} {platform.machine()}"

    # Check CUDA
    is_cuda, device_name, device_count, memory = _check_cuda_available()
    if is_cuda:
        return HardwareInfo(
            device_type=DeviceType.CUDA,
            device_name=device_name,
            device_count=device_count,
            memory_gb=memory,
            platform_info=platform_info,
        )

    # Check MPS
    is_mps, chip_name, memory = _check_mps_available()
    if is_mps:
        return HardwareInfo(
            device_type=DeviceType.MPS,
            device_name=chip_name,
            device_count=1,
            memory_gb=memory,
            platform_info=platform_info,
        )

    # Check XPU
    is_xpu, device_name, device_count, memory = _check_xpu_available()
    if is_xpu:
        return HardwareInfo(
            device_type=DeviceType.XPU,
            device_name=device_name,
            device_count=device_count,
            memory_gb=memory,
            platform_info=platform_info,
        )

    # CPU fallback
    return HardwareInfo(
        device_type=DeviceType.CPU,
        device_name=f"{platform.processor()} or equivalent",
        device_count=1,
        memory_gb=None,  # Could add system RAM detection if needed
        platform_info=platform_info,
    )


def get_device_for_docling(device_preference: Optional[str] = None) -> str:
    """Get the device string compatible with Docling's AcceleratorDevice.

    Args:
        device_preference: Optional device preference ('auto', 'cpu', 'cuda', 'mps', 'xpu')
                          If 'auto' or None, auto-detection is performed.

    Returns:
        str: Device string compatible with Docling's AcceleratorDevice enum

    Example:
        >>> device = get_device_for_docling('auto')
        >>> print(device)
        mps

        >>> # Use with Docling
        >>> from docling.datamodel.accelerator_options import AcceleratorOptions
        >>> accelerator_options = AcceleratorOptions(device=device)
    """
    if device_preference and device_preference.lower() != "auto":
        # Validate the preference
        valid_devices = {d.value for d in DeviceType}
        if device_preference.lower() in valid_devices:
            return device_preference.lower()
        else:
            logger.warning(
                f"Invalid device preference '{device_preference}', using auto-detection"
            )

    # Auto-detect
    detected = detect_device()
    return detected.value


def is_gpu_acceleration_available() -> bool:
    """Quick check if any GPU acceleration is available.

    Returns:
        bool: True if GPU acceleration is available, False otherwise
    """
    device = detect_device()
    return device.is_gpu


# Module-level cached hardware info (computed once on first access)
_cached_hardware_info: Optional[HardwareInfo] = None


def get_cached_hardware_info() -> HardwareInfo:
    """Get cached hardware info (computed once and reused).

    This is more efficient than get_hardware_info() when called multiple times,
    as hardware configuration typically doesn't change during runtime.

    Returns:
        HardwareInfo: Cached hardware information
    """
    global _cached_hardware_info
    if _cached_hardware_info is None:
        _cached_hardware_info = get_hardware_info()
        logger.info(f"Hardware detected: {_cached_hardware_info}")
    return _cached_hardware_info

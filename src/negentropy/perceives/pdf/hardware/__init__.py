"""硬件检测与设备配置子路径。

将原 ``hardware.py`` 迁入为 ``detection.py``，
提供统一导出以保持向后兼容。
"""

from __future__ import annotations

from .detection import (
    DeviceType,
    HardwareInfo,
    detect_device,
    get_cached_hardware_info,
    get_device_for_docling,
    get_hardware_info,
)

__all__ = [
    "DeviceType",
    "HardwareInfo",
    "detect_device",
    "get_cached_hardware_info",
    "get_device_for_docling",
    "get_hardware_info",
]

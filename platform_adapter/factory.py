"""
Platform factory detection logic for selecting active adapter.
"""

from __future__ import annotations

import platform
import os
import threading

from platform_adapter.base import BasePlatform
from platform_adapter.linux import LinuxPlatform
from platform_adapter.windows import WindowsPlatform
from platform_adapter.raspberry_pi import RaspberryPiPlatform


class Platform:
    """
    Unified entry point for retrieving the current host platform adapter.
    """

    _instance: BasePlatform | None = None
    _lock = threading.Lock()

    @classmethod
    def current(cls) -> BasePlatform:
        """
        Get the current platform adapter instance (thread-safe singleton).
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._detect_platform()
        return cls._instance

    @classmethod
    def _detect_platform(cls) -> BasePlatform:
        sys_type = platform.system()
        if sys_type == "Windows":
            return WindowsPlatform()
        elif sys_type == "Linux":
            # Check if Raspberry Pi
            is_pi = False
            if os.path.exists("/sys/firmware/devicetree/base/model"):
                try:
                    with open("/sys/firmware/devicetree/base/model", "r") as f:
                        model = f.read().lower()
                        if "raspberry pi" in model or "rpi" in model:
                            is_pi = True
                except Exception:
                    pass
            if is_pi:
                return RaspberryPiPlatform()
            return LinuxPlatform()
        else:
            # Fallback to LinuxPlatform for generic POSIX behavior
            return LinuxPlatform()

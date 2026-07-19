"""
Raspberry Pi-specific Platform Adapter implementation.
"""

from __future__ import annotations

import os
from typing import Any

from platform_adapter.linux import LinuxPlatform


class RaspberryPiPlatform(LinuxPlatform):
    """
    Raspberry Pi execution platform adapter (inherits Linux capabilities).
    """

    def cpu_info(self) -> dict[str, Any]:
        info = super().cpu_info()
        info["model"] = "Raspberry Pi (Unknown Model)"
        info["hardware"] = "BCM"
        info["temperature_c"] = 0.0

        # Query Raspberry Pi model name from device tree
        if os.path.exists("/sys/firmware/devicetree/base/model"):
            try:
                with open("/sys/firmware/devicetree/base/model", "r") as f:
                    info["model"] = f.read().strip().replace("\x00", "")
            except Exception:
                pass

        # Query SoC temperature
        if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_raw = int(f.read().strip())
                    info["temperature_c"] = round(temp_raw / 1000.0, 1)
            except Exception:
                pass

        return info

    def gpio_available(self) -> bool:
        """
        Check if hardware GPIO registers are accessible on the board.
        """
        return os.path.exists("/sys/class/gpio") or os.path.exists("/dev/gpiomem")

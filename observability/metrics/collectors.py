"""
Metrics Collectors for Realtimex.

Gathers resource statistics (CPU, memory, disk) without external dependencies.
"""

from __future__ import annotations

import os
from typing import Any


def get_cpu_usage() -> float:
    """Get approximate CPU utilization percentage from load average."""
    try:
        load = os.getloadavg()[0]
        cpus = os.cpu_count() or 1
        return min(100.0, (load / cpus) * 100.0)
    except Exception:
        return 0.0


def get_memory_usage() -> float:
    """Get resident set size memory utilization of the current process in MB."""
    try:
        # Linux /proc lookup
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return float(parts[1]) / 1024.0
    except Exception:
        pass
    
    # Fallback/cross-platform memory check (if resource module is available)
    try:
        import resource
        # maxrss is in kilobytes on Linux, bytes on macOS
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return float(usage) / 1024.0 if usage > 10000 else float(usage) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def get_disk_usage(path: str = ".") -> dict[str, float]:
    """Get disk statistics of the specified partition in MB."""
    try:
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        used = total - free
        return {
            "total_mb": total / (1024.0 * 1024.0),
            "used_mb": used / (1024.0 * 1024.0),
            "free_mb": free / (1024.0 * 1024.0),
            "percent_used": (used / total) * 100.0 if total > 0 else 0.0,
        }
    except Exception:
        return {
            "total_mb": 0.0,
            "used_mb": 0.0,
            "free_mb": 0.0,
            "percent_used": 0.0,
        }

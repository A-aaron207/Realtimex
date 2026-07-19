"""
Diagnostics Snapshots for Realtimex.

Captures thread dumps, system metrics, and system snapshots.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

from observability.metrics.collectors import get_cpu_usage, get_memory_usage, get_disk_usage


def take_thread_dump() -> list[dict[str, Any]]:
    """Capture list of currently executing threads and their state."""
    threads = []
    for thread in threading.enumerate():
        threads.append({
            "name": thread.name,
            "id": thread.ident,
            "is_alive": thread.is_alive(),
            "is_daemon": thread.daemon,
        })
    return threads


def take_system_snapshot() -> dict[str, Any]:
    """Capture a lightweight diagnostic snapshot of system resources."""
    disk = get_disk_usage()
    return {
        "pid": os.getpid(),
        "timestamp": time.time(),
        "python_version": sys.version,
        "platform": sys.platform,
        "threads": take_thread_dump(),
        "cpu_usage_percent": get_cpu_usage(),
        "memory_usage_mb": get_memory_usage(),
        "disk_usage": disk,
    }

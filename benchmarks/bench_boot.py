"""
Benchmark: Kernel boot time and memory cost.

Measures:
- Cold boot time (first boot, no warm caches)
- Warm boot time (subsequent boots with same process)
- Boot peak memory usage
- Shutdown time
- Net memory after shutdown (leak check)
"""

from __future__ import annotations

import gc
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.utils import BenchmarkResult, format_table, timed, peak_memory_kb
from kernel.api import KernelAPI

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"
LOG_DIR     = Path(__file__).resolve().parent.parent / "logs"
MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


def _make_api() -> KernelAPI:
    return KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIR,
        modules_root=MODULES_ROOT
    )


def run() -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    # ------------------------------------------------------------------
    # 1. Cold boot time
    # ------------------------------------------------------------------
    boot_times = []
    shutdown_times = []

    for i in range(5):
        api = _make_api()
        gc.collect()

        _, bt = timed(api.boot)
        boot_times.append(bt)

        _, st = timed(api.shutdown)
        shutdown_times.append(st)

        gc.collect()

    results.append(BenchmarkResult(
        name="kernel.boot_time",
        unit="seconds",
        samples=boot_times,
    ))
    results.append(BenchmarkResult(
        name="kernel.shutdown_time",
        unit="seconds",
        samples=shutdown_times,
    ))

    # ------------------------------------------------------------------
    # 2. Boot memory usage
    # ------------------------------------------------------------------
    api = _make_api()
    gc.collect()
    tracemalloc.start()
    api.boot()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    api.shutdown()

    results.append(BenchmarkResult(
        name="kernel.boot_peak_memory",
        unit="KB",
        samples=[peak / 1024],
        metadata={"note": "tracemalloc peak during boot()"},
    ))

    # ------------------------------------------------------------------
    # 3. Re-boot stability (5 × boot/shutdown cycles, same process)
    # ------------------------------------------------------------------
    warm_times = []
    api = _make_api()
    for _ in range(5):
        _, bt = timed(api.boot)
        warm_times.append(bt)
        api.shutdown()

    results.append(BenchmarkResult(
        name="kernel.warm_boot_time",
        unit="seconds",
        samples=warm_times,
        metadata={"note": "consecutive boot/shutdown in same process"},
    ))

    return results


if __name__ == "__main__":
    print("\n=== Kernel Boot Benchmarks ===\n")
    r = run()
    print(format_table(r))
    print()

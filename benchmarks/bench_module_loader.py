"""
Benchmark: Module loader — discovery, validation, import, and capability registration.

Measures:
- Full module load pipeline time (all 10+ modules)
- Per-module average load time
- Capability registry lookup latency
- Memory cost of loaded module set
"""

from __future__ import annotations

import gc
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.utils import BenchmarkResult, format_table, timed
from kernel.api import KernelAPI

CONFIG_PATH  = Path(__file__).resolve().parent.parent / "config" / "config.json"
LOG_DIR      = Path(__file__).resolve().parent.parent / "logs"
MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


def run() -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    # ------------------------------------------------------------------
    # 1. Full module load time (measured during boot)
    # ------------------------------------------------------------------
    LOAD_N = 5
    load_times = []
    module_counts = []

    for _ in range(LOAD_N):
        gc.collect()
        api = KernelAPI(
            config_path=CONFIG_PATH,
            log_directory=LOG_DIR,
            modules_root=MODULES_ROOT
        )

        t0 = time.perf_counter()
        api.boot()
        elapsed = time.perf_counter() - t0
        load_times.append(elapsed)

        loader = api._kernel._boot_result.module_loader
        module_counts.append(len(loader._loaded_modules))

        api.shutdown()
        gc.collect()

    module_count = module_counts[0] if module_counts else 0

    results.append(BenchmarkResult(
        name="module_loader.full_load_time",
        unit="seconds",
        samples=load_times,
        metadata={"module_count": module_count},
    ))
    results.append(BenchmarkResult(
        name="module_loader.per_module_load_time",
        unit="ms",
        samples=[t / module_count * 1000 for t in load_times] if module_count else [0],
        metadata={"module_count": module_count},
    ))

    # ------------------------------------------------------------------
    # 2. Capability registry lookup latency
    # ------------------------------------------------------------------
    from capabilities.registry import CapabilityRegistry

    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIR,
        modules_root=MODULES_ROOT
    )
    api.boot()

    registry = api.capability_registry
    all_caps = registry.list_capabilities()

    LOOKUP_N = 1000
    lookup_times = []
    for cap in (all_caps * (LOOKUP_N // max(len(all_caps), 1) + 1))[:LOOKUP_N]:
        t0 = time.perf_counter()
        registry.find(cap)
        lookup_times.append((time.perf_counter() - t0) * 1000)

    results.append(BenchmarkResult(
        name="capability_registry.lookup_latency",
        unit="ms",
        samples=lookup_times,
        metadata={"n": LOOKUP_N, "total_capabilities": len(all_caps)},
    ))

    # ------------------------------------------------------------------
    # 3. Memory cost of loaded modules
    # ------------------------------------------------------------------
    gc.collect()
    tracemalloc.start()
    _ = api._kernel._boot_result.module_loader._loaded_modules
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results.append(BenchmarkResult(
        name="module_loader.memory_footprint",
        unit="KB",
        samples=[peak / 1024],
        metadata={"module_count": module_count},
    ))

    api.shutdown()
    return results


if __name__ == "__main__":
    print("\n=== Module Loader Benchmarks ===\n")
    r = run()
    print(format_table(r))
    print()

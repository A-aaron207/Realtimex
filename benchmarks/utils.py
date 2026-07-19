"""
Shared benchmark utilities — timing, memory sampling, and result formatting.
"""

from __future__ import annotations

import gc
import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class BenchmarkResult:
    name: str
    unit: str
    samples: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    @property
    def min(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "samples": len(self.samples),
            "mean": round(self.mean, 4),
            "median": round(self.median, 4),
            "stdev": round(self.stdev, 4),
            "min": round(self.min, 4),
            "max": round(self.max, 4),
            "p95": round(self.p95, 4),
            "metadata": self.metadata,
        }


def timed(fn: Callable, *args, **kwargs) -> tuple[Any, float]:
    """Run fn and return (result, elapsed_seconds)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - t0


def repeat(fn: Callable, n: int, warmup: int = 1, *args, **kwargs) -> list[float]:
    """Run fn n times (after warmup) and return elapsed seconds per run."""
    for _ in range(warmup):
        fn(*args, **kwargs)
    times = []
    for _ in range(n):
        gc.collect()
        _, elapsed = timed(fn, *args, **kwargs)
        times.append(elapsed)
    return times


def peak_memory_kb(fn: Callable, *args, **kwargs) -> tuple[Any, float]:
    """Run fn and return (result, peak_memory_KB)."""
    gc.collect()
    tracemalloc.start()
    result = fn(*args, **kwargs)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak / 1024


def format_table(results: list[BenchmarkResult]) -> str:
    """Render results as an ASCII table."""
    header = f"{'Benchmark':<45} {'Mean':>10} {'Median':>10} {'p95':>10} {'Min':>10} {'Max':>10}  Unit"
    sep = "-" * len(header)
    rows = [header, sep]
    for r in results:
        rows.append(
            f"{r.name:<45} {r.mean:>10.4f} {r.median:>10.4f} "
            f"{r.p95:>10.4f} {r.min:>10.4f} {r.max:>10.4f}  {r.unit}"
        )
    return "\n".join(rows)

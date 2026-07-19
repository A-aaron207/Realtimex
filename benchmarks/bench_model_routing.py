"""
Benchmark: Model Gateway routing latency.

Measures:
- Single model request latency
- Throughput under sequential load
- Latency distribution (p50/p95/p99)
- Provider failover overhead
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.utils import BenchmarkResult, format_table
from services.registry import ServiceRegistry
from models.provider import ModelRequest
from kernel.api import KernelAPI

CONFIG_PATH  = Path(__file__).resolve().parent.parent / "config" / "config.json"
LOG_DIR      = Path(__file__).resolve().parent.parent / "logs"
MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


def _get_gateway():
    registry = ServiceRegistry.get_instance()
    gateway_service = registry.get("model_gateway")
    return gateway_service.metadata["gateway"]


def _make_request(prompt: str = "Summarize: benchmark test") -> ModelRequest:
    return ModelRequest(
        task_id="bench_routing",
        request_type="generate",
        capability_required="reasoning",
        prompt=prompt,
        preferred_model="llama3-70b-8192",
    )


def run() -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIR,
        modules_root=MODULES_ROOT
    )
    api.boot()

    gateway = _get_gateway()

    # ------------------------------------------------------------------
    # 1. Single request latency
    # ------------------------------------------------------------------
    SINGLE_N = 30
    latencies = []
    for _ in range(SINGLE_N):
        req = _make_request()
        t0 = time.perf_counter()
        asyncio.run(gateway.generate(req))
        latencies.append((time.perf_counter() - t0) * 1000)

    results.append(BenchmarkResult(
        name="model_gateway.request_latency",
        unit="ms",
        samples=latencies,
        metadata={"n": SINGLE_N, "model": "llama3-70b-8192"},
    ))

    # ------------------------------------------------------------------
    # 2. Sequential throughput
    # ------------------------------------------------------------------
    THROUGHPUT_N = 50
    t0 = time.perf_counter()
    for _ in range(THROUGHPUT_N):
        asyncio.run(gateway.generate(_make_request()))
    elapsed = time.perf_counter() - t0
    throughput = THROUGHPUT_N / elapsed

    results.append(BenchmarkResult(
        name="model_gateway.sequential_throughput",
        unit="req/sec",
        samples=[throughput],
        metadata={"n": THROUGHPUT_N, "elapsed_s": round(elapsed, 3)},
    ))

    # ------------------------------------------------------------------
    # 3. Routing overhead (measure just routing decision, not model call)
    #    Approximate by timing get_instance() + route selection vs full call
    # ------------------------------------------------------------------
    ROUTE_N = 200
    route_times = []
    for _ in range(ROUTE_N):
        t0 = time.perf_counter()
        _ = ServiceRegistry.get_instance()
        route_times.append((time.perf_counter() - t0) * 1000)

    results.append(BenchmarkResult(
        name="model_gateway.registry_lookup_latency",
        unit="ms",
        samples=route_times,
        metadata={"n": ROUTE_N, "note": "ServiceRegistry.get_instance() overhead"},
    ))

    api.shutdown()
    return results


if __name__ == "__main__":
    print("\n=== Model Gateway Benchmarks ===\n")
    r = run()
    print(format_table(r))
    print()

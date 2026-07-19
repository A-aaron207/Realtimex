"""
Benchmark: Event Bus throughput and latency.

Measures:
- Single event publish latency (sync)
- Burst publish throughput (N events/sec)
- Subscribe + receive round-trip latency
- Concurrent publisher throughput
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from benchmarks.utils import BenchmarkResult, format_table
from events.event import Event
from events.event_bus import EventBus
from events.event_types import TaskEventType


def _make_bus() -> EventBus:
    logger = logging.getLogger("benchmarks.event_bus")
    bus = EventBus(logger=logger)
    bus.start()
    return bus


def _make_event(i: int = 0) -> Event:
    return Event(
        name=TaskEventType.TASK_CREATED,
        source="bench",
        payload={"index": i},
    )


def run() -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    # ------------------------------------------------------------------
    # 1. Single publish latency
    # ------------------------------------------------------------------
    SINGLE_N = 500
    bus = _make_bus()
    latencies = []
    for i in range(SINGLE_N):
        t0 = time.perf_counter()
        bus.publish(_make_event(i))
        latencies.append((time.perf_counter() - t0) * 1000)   # ms
    bus.shutdown()

    results.append(BenchmarkResult(
        name="event_bus.publish_latency",
        unit="ms",
        samples=latencies,
        metadata={"n": SINGLE_N},
    ))

    # ------------------------------------------------------------------
    # 2. Burst throughput (events/second)
    # ------------------------------------------------------------------
    BURST_N = 2000
    bus = _make_bus()
    t0 = time.perf_counter()
    for i in range(BURST_N):
        bus.publish(_make_event(i))
    elapsed = time.perf_counter() - t0
    bus.shutdown()
    throughput = BURST_N / elapsed

    results.append(BenchmarkResult(
        name="event_bus.burst_throughput",
        unit="events/sec",
        samples=[throughput],
        metadata={"n": BURST_N, "elapsed_s": round(elapsed, 4)},
    ))

    # ------------------------------------------------------------------
    # 3. Subscribe + receive round-trip latency
    # ------------------------------------------------------------------
    RTT_N = 200
    rtt_times = []

    for _ in range(RTT_N):
        bus = _make_bus()
        received = threading.Event()
        ts_sent = [0.0]
        ts_received = [0.0]

        def handler(event: Event) -> None:
            ts_received[0] = time.perf_counter()
            received.set()

        bus.subscribe(TaskEventType.TASK_CREATED, handler)
        ts_sent[0] = time.perf_counter()
        bus.publish(_make_event())
        received.wait(timeout=1.0)
        bus.shutdown()

        if ts_received[0] > 0:
            rtt_times.append((ts_received[0] - ts_sent[0]) * 1000)

    results.append(BenchmarkResult(
        name="event_bus.subscribe_rtt_latency",
        unit="ms",
        samples=rtt_times,
        metadata={"n": RTT_N},
    ))

    # ------------------------------------------------------------------
    # 4. Concurrent publishers
    # ------------------------------------------------------------------
    CONC_THREADS = 8
    CONC_PER_THREAD = 250
    bus = _make_bus()
    barrier = threading.Barrier(CONC_THREADS)
    thread_times: list[float] = []
    lock = threading.Lock()

    def publish_batch() -> None:
        barrier.wait()
        t0 = time.perf_counter()
        for i in range(CONC_PER_THREAD):
            bus.publish(_make_event(i))
        elapsed = time.perf_counter() - t0
        with lock:
            thread_times.append(elapsed)

    threads = [threading.Thread(target=publish_batch) for _ in range(CONC_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    bus.shutdown()

    total_events = CONC_THREADS * CONC_PER_THREAD
    wall_time = max(thread_times)
    conc_throughput = total_events / wall_time

    results.append(BenchmarkResult(
        name="event_bus.concurrent_throughput",
        unit="events/sec",
        samples=[conc_throughput],
        metadata={
            "threads": CONC_THREADS,
            "events_per_thread": CONC_PER_THREAD,
            "total_events": total_events,
        },
    ))

    return results


if __name__ == "__main__":
    print("\n=== Event Bus Benchmarks ===\n")
    r = run()
    print(format_table(r))
    print()

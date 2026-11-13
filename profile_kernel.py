#!/usr/bin/env python3
"""
Realtimex Kernel — Comprehensive Performance Profiler

Measures:
  1. Startup time (cold boot)
  2. Memory usage (baseline + under load)
  3. Event throughput (publish + dispatch rate)
  4. Scheduler latency (enqueue-to-dispatch)
  5. Worker utilization (execution cycle timing)
  6. Model routing latency (adapter selection + simulated generation)
  7. Task throughput (create + transition rate)

Outputs a structured JSON report and a human-readable summary.
"""

from __future__ import annotations

import asyncio
import gc
import json
import os
import resource
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Ensure Realtimex is importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Data structures for results
# ---------------------------------------------------------------------------

@dataclass
class TimingResult:
    name: str
    samples: list[float] = field(default_factory=list)
    
    @property
    def min_ms(self) -> float:
        return min(self.samples) * 1000 if self.samples else 0.0
    
    @property
    def max_ms(self) -> float:
        return max(self.samples) * 1000 if self.samples else 0.0
    
    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.samples) * 1000 if self.samples else 0.0
    
    @property
    def median_ms(self) -> float:
        return statistics.median(self.samples) * 1000 if self.samples else 0.0
    
    @property
    def p95_ms(self) -> float:
        if len(self.samples) < 2:
            return self.max_ms
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * 0.95)
        return sorted_s[min(idx, len(sorted_s) - 1)] * 1000
    
    @property
    def p99_ms(self) -> float:
        if len(self.samples) < 2:
            return self.max_ms
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * 0.99)
        return sorted_s[min(idx, len(sorted_s) - 1)] * 1000

    @property
    def throughput_per_sec(self) -> float:
        total_time = sum(self.samples)
        if total_time == 0:
            return 0.0
        return len(self.samples) / total_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": len(self.samples),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "throughput_per_sec": round(self.throughput_per_sec, 1),
        }


# ---------------------------------------------------------------------------
# Profiler
# ---------------------------------------------------------------------------

class RealtimexProfiler:
    def __init__(self) -> None:
        self.results: dict[str, Any] = {}
        self._temp_dir = tempfile.mkdtemp(prefix="rtx_profile_")

    # -----------------------------------------------------------------------
    # 1. Startup Time
    # -----------------------------------------------------------------------
    def profile_startup(self, iterations: int = 5) -> TimingResult:
        """Measure cold boot time across multiple iterations."""
        from kernel.boot import BootPaths, run_boot_sequence
        from kernel.logger import KernelLogger

        timing = TimingResult(name="startup_time")

        for i in range(iterations):
            # Reset logger state for clean boot
            KernelLogger._configured = False

            iter_dir = Path(self._temp_dir) / f"boot_{i}"
            iter_dir.mkdir(parents=True, exist_ok=True)
            log_dir = iter_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            modules_dir = iter_dir / "modules"
            modules_dir.mkdir(parents=True, exist_ok=True)

            paths = BootPaths(
                config_path=PROJECT_ROOT / "config" / "config.json",
                log_directory=log_dir,
                modules_root=modules_dir,
            )

            gc.collect()
            start = time.perf_counter()
            boot_result = run_boot_sequence(paths)
            elapsed = time.perf_counter() - start
            timing.samples.append(elapsed)

            # Clean shutdown
            try:
                boot_result.scheduler.stop(timeout=2.0)
            except Exception:
                pass
            try:
                boot_result.event_bus.shutdown(timeout=2.0)
            except Exception:
                pass
            try:
                boot_result.interface_manager.stop_all()
            except Exception:
                pass

            # Reset logger for next iteration
            import logging
            root = logging.getLogger("realtimex")
            root.handlers.clear()
            KernelLogger._configured = False

        self.results["startup"] = timing.to_dict()
        return timing

    # -----------------------------------------------------------------------
    # 2. Memory Usage
    # -----------------------------------------------------------------------
    def profile_memory(self) -> dict[str, Any]:
        """Measure memory footprint at baseline and under load."""
        from kernel.boot import BootPaths, run_boot_sequence
        from kernel.logger import KernelLogger
        from tasks.task import TaskPriority

        KernelLogger._configured = False

        iter_dir = Path(self._temp_dir) / "memory_profile"
        log_dir = iter_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        modules_dir = iter_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)

        gc.collect()
        tracemalloc.start()

        # Baseline: before boot
        baseline_snapshot = tracemalloc.take_snapshot()
        baseline_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        paths = BootPaths(
            config_path=PROJECT_ROOT / "config" / "config.json",
            log_directory=log_dir,
            modules_root=modules_dir,
        )

        boot_result = run_boot_sequence(paths)

        # After boot snapshot
        post_boot_snapshot = tracemalloc.take_snapshot()
        post_boot_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _, post_boot_peak = tracemalloc.get_traced_memory()

        # Generate load: create 500 tasks + 500 memory records
        for i in range(500):
            boot_result.task_manager.create_task(
                goal=f"Profiling task {i}",
                priority=TaskPriority.NORMAL,
            )

        for i in range(500):
            boot_result.memory_manager.create(
                scope="ephemeral",
                owner=f"profiler-{i}",
                content={"data": f"test payload {i}" * 10},
                source="profiler",
                tags=["benchmark", f"batch-{i % 10}"],
                ttl_seconds=300,
            )

        # Under load snapshot
        under_load_snapshot = tracemalloc.take_snapshot()
        under_load_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _, under_load_peak = tracemalloc.get_traced_memory()

        tracemalloc.stop()

        # Compute stats from tracemalloc top
        top_stats = under_load_snapshot.compare_to(post_boot_snapshot, "lineno")[:10]
        top_allocators = []
        for stat in top_stats:
            top_allocators.append({
                "file": str(stat.traceback),
                "size_diff_kb": round(stat.size_diff / 1024, 1),
                "size_kb": round(stat.size / 1024, 1),
                "count_diff": stat.count_diff,
            })

        result = {
            "baseline_rss_mb": round(baseline_rss_kb / 1024, 2),
            "post_boot_rss_mb": round(post_boot_rss_kb / 1024, 2),
            "boot_memory_delta_mb": round((post_boot_rss_kb - baseline_rss_kb) / 1024, 2),
            "post_boot_traced_peak_mb": round(post_boot_peak / (1024 * 1024), 2),
            "under_load_rss_mb": round(under_load_rss_kb / 1024, 2),
            "under_load_traced_peak_mb": round(under_load_peak / (1024 * 1024), 2),
            "load_objects": "500 tasks + 500 memory records",
            "top_allocators_under_load": top_allocators,
        }

        # Cleanup
        try:
            boot_result.scheduler.stop(timeout=2.0)
        except Exception:
            pass
        try:
            boot_result.event_bus.shutdown(timeout=2.0)
        except Exception:
            pass
        try:
            boot_result.interface_manager.stop_all()
        except Exception:
            pass

        import logging
        logging.getLogger("realtimex").handlers.clear()
        from kernel.logger import KernelLogger
        KernelLogger._configured = False

        self.results["memory"] = result
        return result

    # -----------------------------------------------------------------------
    # 3. Event Throughput
    # -----------------------------------------------------------------------
    def profile_event_throughput(self, event_count: int = 10000) -> dict[str, Any]:
        """Measure event publish and dispatch rates."""
        import logging
        from events.bus import EventBus
        from events.event import Event, EventPriority
        from events.filters import EventFilter

        logger = logging.getLogger("profiler.events")
        logger.setLevel(logging.WARNING)  # Suppress INFO noise

        # Test 1: Synchronous dispatch (auto_start=False)
        bus_sync = EventBus(logger=logger, auto_start=False)
        received_count = 0

        def counter_handler(event: Event) -> None:
            nonlocal received_count
            received_count += 1

        bus_sync.subscribe("BenchmarkEvent", counter_handler)

        publish_times: list[float] = []
        for i in range(event_count):
            evt = Event(name="BenchmarkEvent", source="profiler", payload={"i": i})
            t0 = time.perf_counter()
            bus_sync.publish(evt)
            publish_times.append(time.perf_counter() - t0)

        # Dispatch all synchronously
        t0 = time.perf_counter()
        dispatched = bus_sync.dispatch()
        sync_dispatch_time = time.perf_counter() - t0

        # Test 2: Async dispatch (auto_start=True)
        bus_async = EventBus(logger=logger, auto_start=True)
        async_received = threading.Event()
        async_count = 0
        target_count = event_count

        def async_counter(event: Event) -> None:
            nonlocal async_count
            async_count += 1
            if async_count >= target_count:
                async_received.set()

        bus_async.subscribe("AsyncBench", async_counter)

        t0 = time.perf_counter()
        for i in range(event_count):
            bus_async.publish(Event(name="AsyncBench", source="profiler", payload={"i": i}))
        publish_burst_time = time.perf_counter() - t0

        # Wait for all events to be delivered
        async_received.wait(timeout=30.0)
        async_total_time = time.perf_counter() - t0

        bus_async.shutdown(timeout=5.0)

        # Test 3: Fan-out (1 event -> N subscribers)
        bus_fanout = EventBus(logger=logger, auto_start=False)
        fanout_count = 0
        num_subscribers = 50

        def fanout_handler(event: Event) -> None:
            nonlocal fanout_count
            fanout_count += 1

        for _ in range(num_subscribers):
            bus_fanout.subscribe("FanoutEvent", fanout_handler)

        fanout_events = 1000
        for i in range(fanout_events):
            bus_fanout.publish(Event(name="FanoutEvent", source="profiler", payload={"i": i}))

        t0 = time.perf_counter()
        bus_fanout.dispatch()
        fanout_dispatch_time = time.perf_counter() - t0

        result = {
            "event_count": event_count,
            "publish_latency": TimingResult(name="event_publish", samples=publish_times).to_dict(),
            "sync_dispatch": {
                "events_dispatched": dispatched,
                "total_time_ms": round(sync_dispatch_time * 1000, 3),
                "throughput_per_sec": round(dispatched / sync_dispatch_time, 1) if sync_dispatch_time > 0 else 0,
            },
            "async_dispatch": {
                "events_published": event_count,
                "burst_publish_time_ms": round(publish_burst_time * 1000, 3),
                "total_delivery_time_ms": round(async_total_time * 1000, 3),
                "delivery_throughput_per_sec": round(event_count / async_total_time, 1) if async_total_time > 0 else 0,
                "events_received": async_count,
            },
            "fanout": {
                "events": fanout_events,
                "subscribers": num_subscribers,
                "total_deliveries": fanout_count,
                "dispatch_time_ms": round(fanout_dispatch_time * 1000, 3),
                "deliveries_per_sec": round(fanout_count / fanout_dispatch_time, 1) if fanout_dispatch_time > 0 else 0,
            },
        }

        self.results["event_throughput"] = result
        return result

    # -----------------------------------------------------------------------
    # 4. Scheduler Latency
    # -----------------------------------------------------------------------
    def profile_scheduler_latency(self, task_count: int = 200) -> dict[str, Any]:
        """Measure scheduler enqueue and processing latency."""
        from kernel.boot import BootPaths, run_boot_sequence
        from kernel.logger import KernelLogger
        from tasks.task import TaskPriority

        KernelLogger._configured = False
        import logging
        logging.getLogger("realtimex").handlers.clear()

        iter_dir = Path(self._temp_dir) / "scheduler_profile"
        log_dir = iter_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        modules_dir = iter_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)

        paths = BootPaths(
            config_path=PROJECT_ROOT / "config" / "config.json",
            log_directory=log_dir,
            modules_root=modules_dir,
        )

        boot_result = run_boot_sequence(paths)

        # Measure task creation + workflow creation latency (scheduler enqueue path)
        task_create_timing = TimingResult(name="task_creation")
        workflow_create_timing = TimingResult(name="workflow_creation")

        tasks = []
        for i in range(task_count):
            t0 = time.perf_counter()
            task = boot_result.task_manager.create_task(
                goal=f"Scheduler benchmark task {i}",
                priority=TaskPriority.NORMAL,
            )
            task_create_timing.samples.append(time.perf_counter() - t0)
            tasks.append(task)

        # Measure workflow creation (triggers scheduler enqueue)
        for task in tasks[:50]:  # Only profile 50 workflows
            step_defs = [
                {"step_id": "step_1", "capability": "plan_task", "input_data": {}, "dependencies": []},
                {"step_id": "step_2", "capability": "web_search", "input_data": {}, "dependencies": ["step_1"]},
            ]
            t0 = time.perf_counter()
            boot_result.workflow_manager.create_workflow(
                parent_task_id=task.task_id,
                step_definitions=step_defs,
            )
            workflow_create_timing.samples.append(time.perf_counter() - t0)

        # Let scheduler process for a moment
        time.sleep(1.0)

        scheduler_metrics = boot_result.scheduler.metrics()

        # Cleanup
        boot_result.scheduler.stop(timeout=2.0)
        boot_result.event_bus.shutdown(timeout=2.0)
        try:
            boot_result.interface_manager.stop_all()
        except Exception:
            pass

        logging.getLogger("realtimex").handlers.clear()
        KernelLogger._configured = False

        result = {
            "task_creation": task_create_timing.to_dict(),
            "workflow_creation": workflow_create_timing.to_dict(),
            "scheduler_metrics": scheduler_metrics,
        }

        self.results["scheduler_latency"] = result
        return result

    # -----------------------------------------------------------------------
    # 5. Worker Utilization
    # -----------------------------------------------------------------------
    def profile_worker_utilization(self) -> dict[str, Any]:
        """Measure worker execution cycle timing."""
        from kernel.boot import BootPaths, run_boot_sequence
        from kernel.logger import KernelLogger
        from workers.runtime import WorkerRuntime
        from workers.context import ExecutionContext
        from tasks.task import TaskPriority

        KernelLogger._configured = False
        import logging
        logging.getLogger("realtimex").handlers.clear()

        iter_dir = Path(self._temp_dir) / "worker_profile"
        log_dir = iter_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        modules_dir = iter_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)

        paths = BootPaths(
            config_path=PROJECT_ROOT / "config" / "config.json",
            log_directory=log_dir,
            modules_root=modules_dir,
        )

        boot_result = run_boot_sequence(paths)

        # Create a test task
        task = boot_result.task_manager.create_task(
            goal="Worker benchmark task",
            priority=TaskPriority.NORMAL,
        )

        # Create a workflow so we have steps
        step_defs = [
            {"step_id": "bench_step", "capability": "plan_task", "input_data": {"prompt": "Benchmark test"}, "dependencies": []},
        ]
        wf = boot_result.workflow_manager.create_workflow(
            parent_task_id=task.task_id,
            step_definitions=step_defs,
        )

        # Profile individual worker execution cycles
        execution_timing = TimingResult(name="worker_execution_cycle")
        workers = boot_result.worker_manager.list_workers()

        worker_details = []
        for w in workers:
            worker_details.append({
                "worker_id": w.worker_id,
                "type": w.worker_type,
                "capability": w.supported_capability,
                "state": str(w.state),
            })

        # Execute steps directly on workers to measure raw execution time
        step = list(wf.steps.values())[0]
        for i in range(100):
            ctx = ExecutionContext(
                task_id=task.task_id,
                step_id=step.step_id,
                workflow_id=wf.workflow_id,
                capability=step.capability,
                input=step.input_data,
            )

            # Find a matching worker
            matching_workers = [w for w in workers if w.supported_capability == step.capability]
            if matching_workers:
                worker = matching_workers[0]
                t0 = time.perf_counter()
                try:
                    worker.execute(ctx)
                except Exception:
                    pass
                execution_timing.samples.append(time.perf_counter() - t0)

        # Cleanup
        boot_result.scheduler.stop(timeout=2.0)
        boot_result.event_bus.shutdown(timeout=2.0)
        try:
            boot_result.interface_manager.stop_all()
        except Exception:
            pass

        logging.getLogger("realtimex").handlers.clear()
        KernelLogger._configured = False

        result = {
            "worker_count": len(workers),
            "workers": worker_details,
            "execution_cycle": execution_timing.to_dict(),
        }

        self.results["worker_utilization"] = result
        return result

    # -----------------------------------------------------------------------
    # 6. Model Routing Latency
    # -----------------------------------------------------------------------
    def profile_model_routing(self, request_count: int = 100) -> dict[str, Any]:
        """Measure model gateway initialization, routing, and generation latency."""
        from models.gateway import ModelGateway
        from models.provider import ModelRequest

        loop = asyncio.new_event_loop()

        # Initialize gateway
        gateway = ModelGateway()
        t0 = time.perf_counter()
        loop.run_until_complete(gateway.initialize())
        init_time = time.perf_counter() - t0

        # Profile model selection/routing latency
        routing_timing = TimingResult(name="model_routing")
        generation_timing = TimingResult(name="model_generation")

        for i in range(request_count):
            request = ModelRequest(
                task_id=f"bench-task-{i}",
                request_type="generation",
                capability_required="reasoning",
                prompt=f"Benchmark prompt number {i}: Explain the concept of event-driven architecture.",
                constraints=["max_tokens:100"],
                parameters={"temperature": 0.7},
            )

            # Route selection only
            t0 = time.perf_counter()
            try:
                selected = gateway.router.select_model(request)
            except Exception:
                selected = None
            routing_timing.samples.append(time.perf_counter() - t0)

            # Full generation (includes simulated network delay)
            t0 = time.perf_counter()
            try:
                response = loop.run_until_complete(gateway.generate(request))
            except Exception:
                pass
            generation_timing.samples.append(time.perf_counter() - t0)

        # Cache hit rate
        cache_stats = {
            "total_requests": gateway.metrics.total_requests,
            "cache_hits": gateway.metrics.cache_hits,
            "cache_misses": gateway.metrics.cache_misses,
            "cache_hit_rate_pct": round(gateway.metrics.cache_hits / max(gateway.metrics.total_requests, 1) * 100, 1),
        }

        loop.close()

        result = {
            "gateway_init_time_ms": round(init_time * 1000, 3),
            "routing_selection": routing_timing.to_dict(),
            "full_generation": generation_timing.to_dict(),
            "cache_stats": cache_stats,
            "registered_providers": list(gateway.registry.list_providers()),
            "registered_models": len(gateway.registry.list_models()),
        }

        self.results["model_routing"] = result
        return result

    # -----------------------------------------------------------------------
    # 7. Task Throughput
    # -----------------------------------------------------------------------
    def profile_task_throughput(self, task_count: int = 1000) -> dict[str, Any]:
        """Measure task creation, state transition, and query throughput."""
        from kernel.boot import BootPaths, run_boot_sequence
        from kernel.logger import KernelLogger
        from tasks.task import TaskPriority
        from tasks.states import TaskState

        KernelLogger._configured = False
        import logging
        logging.getLogger("realtimex").handlers.clear()

        iter_dir = Path(self._temp_dir) / "task_throughput"
        log_dir = iter_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        modules_dir = iter_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)

        paths = BootPaths(
            config_path=PROJECT_ROOT / "config" / "config.json",
            log_directory=log_dir,
            modules_root=modules_dir,
        )

        boot_result = run_boot_sequence(paths)

        # Profile task creation throughput
        create_timing = TimingResult(name="task_create")
        tasks = []
        for i in range(task_count):
            t0 = time.perf_counter()
            task = boot_result.task_manager.create_task(
                goal=f"Throughput benchmark task {i}",
                priority=[TaskPriority.LOW, TaskPriority.NORMAL, TaskPriority.HIGH][i % 3],
                metadata={"batch": i // 100, "index": i},
            )
            create_timing.samples.append(time.perf_counter() - t0)
            tasks.append(task)

        # Profile state transitions
        transition_timing = TimingResult(name="task_transition")
        for task in tasks[:500]:  # Transition first 500
            t0 = time.perf_counter()
            boot_result.task_manager.transition(task.task_id, TaskState.PLANNING)
            transition_timing.samples.append(time.perf_counter() - t0)

        # Profile task retrieval
        retrieve_timing = TimingResult(name="task_retrieve")
        for task in tasks[:500]:
            t0 = time.perf_counter()
            boot_result.task_manager.get_task(task.task_id)
            retrieve_timing.samples.append(time.perf_counter() - t0)

        # Profile listing/querying
        list_timing = TimingResult(name="task_list_all")
        for _ in range(20):
            t0 = time.perf_counter()
            boot_result.task_manager.list_tasks()
            list_timing.samples.append(time.perf_counter() - t0)

        # Cleanup
        boot_result.scheduler.stop(timeout=2.0)
        boot_result.event_bus.shutdown(timeout=2.0)
        try:
            boot_result.interface_manager.stop_all()
        except Exception:
            pass

        logging.getLogger("realtimex").handlers.clear()
        KernelLogger._configured = False

        result = {
            "task_count": task_count,
            "create": create_timing.to_dict(),
            "transition": transition_timing.to_dict(),
            "retrieve": retrieve_timing.to_dict(),
            "list_all": list_timing.to_dict(),
        }

        self.results["task_throughput"] = result
        return result

    # -----------------------------------------------------------------------
    # Run all profiles
    # -----------------------------------------------------------------------
    def run_all(self) -> dict[str, Any]:
        """Execute all profiling benchmarks and return combined results."""
        print("=" * 70)
        print("  REALTIMEX KERNEL — PERFORMANCE PROFILER")
        print("=" * 70)

        print("\n[1/7] Profiling startup time...")
        self.profile_startup(iterations=5)

        print("[2/7] Profiling memory usage...")
        self.profile_memory()

        print("[3/7] Profiling event throughput...")
        self.profile_event_throughput(event_count=10000)

        print("[4/7] Profiling scheduler latency...")
        self.profile_scheduler_latency(task_count=200)

        print("[5/7] Profiling worker utilization...")
        self.profile_worker_utilization()

        print("[6/7] Profiling model routing latency...")
        self.profile_model_routing(request_count=100)

        print("[7/7] Profiling task throughput...")
        self.profile_task_throughput(task_count=1000)

        print("\nAll benchmarks complete.\n")
        return self.results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    profiler = RealtimexProfiler()
    results = profiler.run_all()

    # Write JSON report
    report_path = PROJECT_ROOT / "logs" / "profile_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"JSON report written to: {report_path}")

    # Print human-readable summary
    print("\n" + "=" * 70)
    print("  PROFILING RESULTS SUMMARY")
    print("=" * 70)

    if "startup" in results:
        s = results["startup"]
        print(f"\n  Startup Time")
        print(f"    Mean:    {s['mean_ms']:.1f} ms")
        print(f"    Median:  {s['median_ms']:.1f} ms")
        print(f"    Min:     {s['min_ms']:.1f} ms")
        print(f"    Max:     {s['max_ms']:.1f} ms")

    if "memory" in results:
        m = results["memory"]
        print(f"\n  Memory Usage")
        print(f"    Post-boot RSS:    {m['post_boot_rss_mb']:.1f} MB")
        print(f"    Under load RSS:   {m['under_load_rss_mb']:.1f} MB")
        print(f"    Traced peak:      {m['under_load_traced_peak_mb']:.1f} MB")

    if "event_throughput" in results:
        e = results["event_throughput"]
        print(f"\n  Event Throughput")
        print(f"    Sync dispatch:    {e['sync_dispatch']['throughput_per_sec']:.0f} events/sec")
        print(f"    Async delivery:   {e['async_dispatch']['delivery_throughput_per_sec']:.0f} events/sec")
        print(f"    Fan-out (50 sub): {e['fanout']['deliveries_per_sec']:.0f} deliveries/sec")

    if "scheduler_latency" in results:
        sl = results["scheduler_latency"]
        print(f"\n  Scheduler Latency")
        print(f"    Task create mean:     {sl['task_creation']['mean_ms']:.3f} ms")
        print(f"    Workflow create mean:  {sl['workflow_creation']['mean_ms']:.3f} ms")

    if "worker_utilization" in results:
        w = results["worker_utilization"]
        print(f"\n  Worker Utilization")
        print(f"    Workers:           {w['worker_count']}")
        print(f"    Exec cycle mean:   {w['execution_cycle']['mean_ms']:.3f} ms")
        print(f"    Exec cycle p95:    {w['execution_cycle']['p95_ms']:.3f} ms")

    if "model_routing" in results:
        mr = results["model_routing"]
        print(f"\n  Model Routing")
        print(f"    Gateway init:      {mr['gateway_init_time_ms']:.1f} ms")
        print(f"    Route select mean: {mr['routing_selection']['mean_ms']:.3f} ms")
        print(f"    Generation mean:   {mr['full_generation']['mean_ms']:.1f} ms")
        print(f"    Cache hit rate:    {mr['cache_stats']['cache_hit_rate_pct']:.1f}%")

    if "task_throughput" in results:
        t = results["task_throughput"]
        print(f"\n  Task Throughput")
        print(f"    Create:     {t['create']['throughput_per_sec']:.0f} tasks/sec (mean {t['create']['mean_ms']:.3f} ms)")
        print(f"    Transition: {t['transition']['throughput_per_sec']:.0f} ops/sec (mean {t['transition']['mean_ms']:.3f} ms)")
        print(f"    Retrieve:   {t['retrieve']['throughput_per_sec']:.0f} ops/sec (mean {t['retrieve']['mean_ms']:.3f} ms)")
        print(f"    List all:   {t['list_all']['mean_ms']:.1f} ms per query ({t['list_all']['count']} runs)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

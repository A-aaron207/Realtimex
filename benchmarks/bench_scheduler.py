"""
Benchmark: Scheduler throughput and Worker utilization.

Measures:
- Task submission latency
- Scheduler dispatch rate (tasks/second)
- Worker pool saturation point
- Parallel task execution scaling (1→2→4→8 workers)
"""

from __future__ import annotations

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.utils import BenchmarkResult, format_table, timed
from kernel.api import KernelAPI

CONFIG_PATH  = Path(__file__).resolve().parent.parent / "config" / "config.json"
LOG_DIR      = Path(__file__).resolve().parent.parent / "logs"
MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


import uuid
from interfaces.cli.interface import CLIInterface
from tasks.states import TaskState

_register_lock = threading.Lock()


def _submit_goal(api: KernelAPI, goal: str) -> dict[str, str]:
    # Use a unique interface type to avoid colliding with default 'cli' or other threads
    unique_id = str(uuid.uuid4())[:8]
    interface_type = f"cli_{unique_id}"
    
    cli = CLIInterface(
        user_id="benchmark_user",
        interactive=False,
        single_command=goal,
        use_colors=False
    )
    # Set the unique interface type
    cli.interface_type = interface_type
    cli.name = f"CLI_{unique_id}"
    
    with _register_lock:
        api.interface_manager.register_interface(cli)
        api.interface_manager.start_interface(interface_type)

    request = api.interface_manager.receive(interface_type)
    if not request:
        with _register_lock:
            api.interface_manager.registry.unregister(interface_type)
        return {}

    response = api.interface_manager.process_request(request)
    
    with _register_lock:
        api.interface_manager.registry.unregister(interface_type)
        
    task_id = response.metadata.get("task_id")
    return {"task_id": task_id} if task_id else {}


def _submit_and_wait(api: KernelAPI, goal: str, timeout: float = 10.0) -> float:
    """Submit a goal, wait for completion, return wall-clock seconds."""
    t0 = time.perf_counter()
    result = _submit_goal(api, goal)
    task_id = result.get("task_id")
    if task_id:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            task = api.task_manager.get_task(task_id)
            if task and task.state in (TaskState.COMPLETED, TaskState.FAILED):
                break
            time.sleep(0.01)
    return time.perf_counter() - t0


def _booted_api() -> KernelAPI:
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIR,
        modules_root=MODULES_ROOT
    )
    api.boot()
    return api


def run() -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    api = _booted_api()

    # ------------------------------------------------------------------
    # 1. Task submission latency (submit only, no wait)
    # ------------------------------------------------------------------
    SUB_N = 20
    sub_latencies = []
    for _ in range(SUB_N):
        t0 = time.perf_counter()
        _submit_goal(api, "Summarize: benchmark test input for submission latency measurement")
        sub_latencies.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.05)   # brief gap to avoid queue overflow

    results.append(BenchmarkResult(
        name="scheduler.task_submission_latency",
        unit="ms",
        samples=sub_latencies,
        metadata={"n": SUB_N},
    ))

    # ------------------------------------------------------------------
    # 2. End-to-end task completion time (sequential)
    # ------------------------------------------------------------------
    SEQ_N = 5
    completion_times = []
    for _ in range(SEQ_N):
        elapsed = _submit_and_wait(api, "Summarize: sequential benchmark task")
        completion_times.append(elapsed)

    results.append(BenchmarkResult(
        name="scheduler.sequential_task_completion",
        unit="seconds",
        samples=completion_times,
        metadata={"n": SEQ_N},
    ))

    # ------------------------------------------------------------------
    # 3. Concurrent task throughput (N simultaneous submissions)
    # ------------------------------------------------------------------
    CONC_N = 8
    conc_times: list[float] = []
    lock = threading.Lock()

    def run_task() -> None:
        elapsed = _submit_and_wait(api, "Summarize: concurrent benchmark task")
        with lock:
            conc_times.append(elapsed)

    t_start = time.perf_counter()
    threads = [threading.Thread(target=run_task) for _ in range(CONC_N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_time = time.perf_counter() - t_start

    throughput = CONC_N / wall_time

    results.append(BenchmarkResult(
        name="scheduler.concurrent_task_throughput",
        unit="tasks/sec",
        samples=[throughput],
        metadata={
            "concurrent_tasks": CONC_N,
            "wall_time_s": round(wall_time, 3),
            "individual_times": [round(t, 3) for t in conc_times],
        },
    ))

    results.append(BenchmarkResult(
        name="scheduler.concurrent_task_latency",
        unit="seconds",
        samples=conc_times,
        metadata={"concurrent_tasks": CONC_N},
    ))

    api.shutdown()
    return results


if __name__ == "__main__":
    print("\n=== Scheduler & Worker Benchmarks ===\n")
    r = run()
    print(format_table(r))
    print()

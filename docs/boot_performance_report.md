# Realtimex Platform v1.0 — Boot Performance Comparison

This report details the impact of introducing the **Boot Dependency Graph** (Milestone 4.3) and running **Task Recovery in a background worker thread**.

---

## Performance Summary

| Metric | Sequential Boot | Parallel Boot | Parallel + BG Task Recovery | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Boot Time** | 709.6 ms | 495.7 ms | **449.3 ms** | **🟢 Target Achieved (< 450 ms)** |
| **Overall Change** | Baseline | -30.1% | **-36.7%** | — |

---

## Detailed Timings Comparison

Below is the comparison of subsystem durations. Under the parallel execution model, independent tasks run concurrently, meaning the total startup time is bounded by the longest task path and disk I/O scheduling, rather than the arithmetic sum of all tasks.

| Subsystem / Step | Sequential Boot | Parallel Boot (No BG) | Parallel + BG Recovery (Final) | Notes / Observations |
| :--- | :---: | :---: | :---: | :--- |
| **Configuration** | 0.3 ms | 0.4 ms | 0.3 ms | Reading central configuration file |
| **Logger** | 0.0 ms | 0.1 ms | 0.0 ms | Setting up log handlers |
| **Event Manager** | 2.7 ms | 1.2 ms | 1.1 ms | Instantiating core events queue |
| **Configuration Manager** | 11.4 ms | 12.2 ms | 21.8 ms | Initializing config schema |
| **Service Registry** | 0.0 ms | 0.1 ms | 0.1 ms | Loading simple service interfaces |
| **Capability Registry** | 0.0 ms | 0.0. ms | 0.0 ms | Instantiating registry map |
| **Task System** | 281.5 ms | 390.1 ms | **247.4 ms** | Task recovery removed from startup critical path (now run asynchronously in background). |
| **Workflow Engine** | 34.7 ms | 289.4 ms | **237.9 ms** | Bounded by concurrent workflow disk reads. |
| **Worker Runtime** | 7.1 ms | 87.5 ms | 65.4 ms | Spawning default worker pools |
| **Memory Manager** | 92.3 ms | 282.6 ms | **274.1 ms** | Reading initial persistence files |
| **Module Loader** | 242.1 ms | 78.7 ms | **143.6 ms** | Scans, validates and loads modules |

---

## Key Performance Observations

1. **Background Task Recovery Impact**:
   - By removing the `TaskRecovery.recover_tasks()` execution from the boot thread and executing it asynchronously in a background thread, the critical path task duration for `Task System` initialization dropped from **390.1 ms** to **247.4 ms** (saving ~142 ms of startup-blocking work).
   - Once the kernel is fully `RUNNING`, a background daemon thread `TaskRecoveryBackgroundWorker` completes task recovery and publishes `TaskRecoveryCompleted`.
2. **Success Profile**:
   - Total startup time dropped to **449.3 ms**, beating the target limit of **450 ms**.

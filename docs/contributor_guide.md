# Realtimex Contributor Guide

Thank you for contributing to Realtimex! This guide outlines how to run unit and integration tests, execute and write performance benchmarks, configure self-hosting development flows, and follow code style and architecture practices.

---

## 1. Testing Suite

Every change to the Realtimex Kernel must pass all unit and integration tests.

### Running Unit Tests
Unit tests discover individual component capabilities under `specs/`:
```bash
python3 -m unittest discover -s specs/
```

### Running Golden Workflows Integration Tests
The Golden Workflows verify end-to-end execution of task flows using `pytest`:
```bash
pytest specs/test_golden_workflows.py
```

---

## 2. Performance Benchmarks

Realtimex measures resource usage, boot speed, event throughput, and latency to guard against performance regressions.

### Running Benchmarks
Run the master performance suite to execute all benchmarks and output a Markdown report to `benchmarks/reports/`:
```bash
python3 benchmarks/runner.py
```

### Target Performance Metrics:
When submitting patches, verify your numbers match or exceed these goals:
- **Kernel Boot Time**: `< 0.5s` (measured sequentially)
- **Kernel Shutdown Time**: `< 0.3s`
- **Event Bus Publish Latency (p95)**: `< 1.0ms`
- **Event Bus Burst Throughput**: `> 10,000 events/second`
- **Event Bus Subscribe Round-Trip Latency (p95)**: `< 5.0ms`
- **Capability Registry Lookup Latency (p95)**: `< 0.1ms`
- **Model Gateway Request Latency**: `< 5.0ms` (simulated local response)

---

## 3. Daily Self-Hosting

The most effective way to test Realtimex is by using Realtimex to develop Realtimex. Use the CLI interface to run test discoveries, generate commits, or search the codebase.

### Example: Running a CLI task
You can use `main.py` to trigger task execution:
```bash
python3 main.py
```

To run Realtimex interactively, launch the interactive CLI interface (details under `interfaces/cli/`):
```python
from interfaces.cli.interface import CLIInterface
cli = CLIInterface(interactive=True)
```

By daily-driving the system, Annoyances become Bug Reports, and friction points become UX features.

---

## 4. Code Style & Architecture Guidelines

### Formatting and Types:
- Follow **PEP 8** style guidelines.
- Use explicit type annotations on all public functions, classes, and method interfaces:
  ```python
  def process_data(input_data: dict[str, Any]) -> list[str]:
  ```

### Thread Safety:
The Realtimex Kernel is heavily multithreaded (with background threads for Event Bus dispatching, Scheduler loop, and Worker pool runs).
- Protect critical sections using `threading.Lock` or re-entrant locks `threading.RLock`:
  ```python
  import threading
  
  class ThreadSafeStore:
      def __init__(self) -> None:
          self._lock = threading.RLock()
          self._data = {}
          
      def set(self, key: str, value: Any) -> None:
          with self._lock:
              self._data[key] = value
  ```
- Always make sure exceptions in subscribers are caught and logged inside the dispatcher, so a single subscriber crash does not bring down the Event Bus dispatch loop.

### Backwards Compatibility:
- Respect shims and backwards-compatibility files (such as `events/event_bus.py` re-exporting the production Event Bus class) so existing Milestone imports remain unbroken.

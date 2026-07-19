# Realtimex Kernel API

The Kernel API exposes the Realtimex Kernel's control surface as a stable entry point for embedding applications and external interfaces (CLI, REST, WebSocket). It abstracts away internal orchestration, providing a clean interface to initialize, monitor, and shutdown the kernel.

---

## Initialization

The `KernelAPI` class is initialized by passing paths to configuration, logs, and modules:

```python
from pathlib import Path
from kernel.api import KernelAPI

PROJECT_ROOT = Path(__file__).resolve().parent

api = KernelAPI(
    config_path=PROJECT_ROOT / "config" / "config.json",
    log_directory=PROJECT_ROOT / "logs",
    modules_root=PROJECT_ROOT / "modules"
)
```

---

## Control Methods

### `boot()`
Runs the full initialization sequence of the kernel. This transitions the lifecycle state to `RUNNING` and initializes all core services.
```python
api.boot()
```

### `shutdown()`
Gracefully shuts down the kernel, flushing all pending tasks and events, and closing system interfaces.
```python
api.shutdown()
```

### `restart()`
Performs a sequential shutdown and boot sequence.
```python
api.restart()
```

### `status() -> dict[str, object]`
Retrieves the current kernel status, including the lifecycle state and summaries of core components:
```python
status_info = api.status()
# Example output:
# {
#     "state": "RUNNING",
#     "uptime": 12.34,
#     "loaded_modules_count": 13,
#     ...
# }
```

---

## Subsystem Access

The `KernelAPI` exposes properties for accessing the core subsystem instances. These will raise a `RuntimeError` if accessed before calling `boot()`.

| Property | Type | Description |
|---|---|---|
| `event_manager` | `EventManager` | Accesses the event infrastructure (bus, history, persistence, replay). |
| `task_manager` | `TaskManager` | Manages task state transitions, tracking, and metadata. |
| `task_api` | `TaskAPI` | Interrogates active and completed tasks. |
| `workflow_manager` | `WorkflowManager` | Orchestrates workflow execution flows. |
| `workflow_api` | `WorkflowAPI` | Interrogates active workflows. |
| `worker_manager` | `WorkerManager` | Manages worker pools, execution, and health monitoring. |
| `worker_api` | `WorkerAPI` | Interrogates worker status and performance metrics. |
| `scheduler` | `Scheduler` | Schedules execution steps. |
| `scheduler_api` | `SchedulerAPI` | Interrogates queue state and resource allocations. |
| `capability_registry`| `CapabilityRegistry` | Looks up which module provides which capability. |
| `interface_manager` | `InterfaceManager` | Manages CLI, REST, and WebSocket communication interfaces. |
| `memory_manager` | `MemoryManager` | Manages short-term and long-term memory records. |
| `model_gateway` | `ModelGateway` | Directs requests to LLM provider endpoints. |
| `cognitive_engine` | `CognitiveEngine` | Drives reasoning and execution plan synthesis. |

---

## Execution Pattern Example

Below is a standard script showcasing how to initialize, boot, run a single-command CLI goal, and shut down the Kernel using the Kernel API:

```python
import time
from kernel.api import KernelAPI
from interfaces.cli.interface import CLIInterface
from tasks.states import TaskState

# 1. Initialize API
api = KernelAPI(
    config_path=Path("config/config.json"),
    log_directory=Path("logs"),
    modules_root=Path("modules")
)

# 2. Boot the Kernel
api.boot()

# 3. Setup CLI Interface and submit task
cli = CLIInterface(
    user_id="user_cli",
    interactive=False,
    single_command="Summarize: Sprint 1 is complete.",
    use_colors=True
)

# Unregister default interface to avoid duplicate type registration
api.interface_manager.registry.unregister("cli")
api.interface_manager.register_interface(cli)
api.interface_manager.start_interface("cli")

# 4. Route and process request
request = api.interface_manager.receive("cli")
if request:
    response = api.interface_manager.process_request(request)
    task_id = response.metadata.get("task_id")
    
    # 5. Wait for task completion
    if task_id:
        while True:
            task = api.task_manager.get_task(task_id)
            if task.state in (TaskState.COMPLETED, TaskState.FAILED):
                print(f"Task completed with state: {task.state}")
                break
            time.sleep(0.1)

# 6. Shutdown the Kernel
api.shutdown()
```

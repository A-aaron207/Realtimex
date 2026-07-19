# Realtimex Recovery System

## Overview

The Recovery System restores the Realtimex Kernel to a consistent state after unexpected interruptions such as crashes, power loss, or forced termination. It prioritizes **state restoration** over execution resumption—the Kernel determines when execution resumes.

## Core Principles

- **Consistency Over Speed**: Recovery always prefers consistency and correctness
- **No Automatic Execution**: Recovery restores state only; the Scheduler determines when to resume
- **Isolation of Corruption**: Invalid data is isolated rather than crashing the kernel
- **Thread-Safe Operations**: All managers use locks to ensure concurrent access safety
- **Event-Driven**: Full integration with the Event System for auditability

## Architecture

### Components

#### RecoveryManager
Core orchestrator that coordinates all recovery operations.

**Key Methods:**
- `recover()` - Recover from the latest checkpoint
- `create_checkpoint()` - Save current system state
- `restore_checkpoint(id)` - Restore from a specific checkpoint
- `create_snapshot()` - Create full system backup
- `restore_snapshot(id)` - Restore from backup
- `validate()` - Validate checkpoint integrity
- `status()` - Show recovery status

**Thread-Safe:** Uses `threading.RLock()` to protect all public methods.

#### CheckpointManager
Handles checkpoint file operations and retention policies.

**Responsibilities:**
- Save/load/delete checkpoints
- Automatic pruning of old checkpoints
- Enforce retention limits

#### SnapshotManager
Manages full-system diagnostic backups.

**Responsibilities:**
- Create full-system snapshots
- Restore snapshot data
- Automatic pruning of old snapshots

#### StateValidator
Validates structural integrity of recovered data.

**Validation Approach:**
- Schema validation (required fields, types)
- Isolation of corrupted items (not crashes)
- Detailed error messages for diagnostics

**Valid Task Statuses:** created, active, completed, failed, pending, running, paused, cancelled

**Valid Workflow Statuses:** created, active, completed, failed, pending, paused

**Valid Memory Scopes:** global, session, task, workflow

#### RecoveryPlanner
Plans recovery sequence based on checkpoint data and policies.

**Recovery Strategies:**

1. **Fail-Safe (Default)**
   - Recovers all valid data
   - Isolates corrupted items
   - Continues despite corruption
   - Suitable for resilient systems

2. **Strict**
   - Aborts recovery if ANY corruption detected
   - Suitable for production systems where consistency is paramount
   - Set via `RecoveryPolicy.recovery_strategy = "strict"`

#### RecoveryPersistence
Manages persistent storage of checkpoints and snapshots on disk.

**Storage Layout:**
```
recovery_base/
├── checkpoints/
│   ├── cp-001.json
│   └── cp-002.json
└── snapshots/
    ├── snap-001.json
    └── snap-002.json
```

#### RecoveryReport
Structured report of recovery outcomes.

**Contents:**
- `recovery_id`: Unique recovery session ID
- `timestamp`: When recovery occurred
- `restored_tasks`: IDs of successfully restored tasks
- `restored_workflows`: IDs of successfully restored workflows
- `failed_restorations`: Details of items that failed
- `warnings`: Non-fatal issues encountered
- `suggested_actions`: Recommended next steps

**Convenience Properties:**
- `is_successful`: Boolean indicating no failures/warnings
- `items_restored`: Total count of restored items
- `items_failed`: Total count of failed items

## Recovery Flow

### Standard Recovery
```
RecoveryStarted Event
    ↓
Load Latest Checkpoint
    ↓
Validate All Data
    ↓
Separate Clean/Isolated Data
    ↓
Apply Recovery Strategy
    ↓
Restore Tasks
    ↓
Restore Workflows
    ↓
Restore Memories
    ↓
Generate Report
    ↓
RecoveryCompleted Event
```

### Fail-Safe vs Strict

**Fail-Safe Strategy:**
```
Corrupted Item Detected
    ↓
Isolated (Logged as Warning)
    ↓
Recovery Continues
    ↓
Report Includes Isolated Items
    ↓
Recovery Completes Successfully
```

**Strict Strategy:**
```
Corrupted Item Detected
    ↓
Raise RecoveryPlannerError
    ↓
Recovery Aborts
    ↓
RecoveryFailed Event
```

## Events Emitted

The Recovery System emits events throughout its operations for full auditability:

- `RecoveryStarted` - Recovery operation initiated
- `CheckpointLoaded` - Checkpoint file loaded
- `StateValidated` - Data validation completed
- `TaskRecovered` - Individual task restored
- `WorkflowRecovered` - Individual workflow restored
- `MemoryRecovered` - Memory reference restored
- `RecoveryCompleted` - Recovery succeeded
- `RecoveryFailed` - Recovery failed
- `SnapshotCreated` - Snapshot backup created
- `SnapshotRestored` - Snapshot loaded

## Configuration

### RecoveryPolicy

```python
from recovery.policies import RecoveryPolicy

policy = RecoveryPolicy(
    checkpoint_interval_seconds=60.0,      # How often to checkpoint
    max_retained_checkpoints=5,             # Max checkpoints to keep
    snapshot_retention_days=30,             # Snapshot retention (informational)
    auto_cleanup_on_start=True,             # Cleanup on boot
    recovery_strategy="fail_safe",          # or "strict"
)
```

### Initialization

```python
from pathlib import Path
from recovery import RecoveryManager, RecoveryPersistence, RecoveryPolicy
from recovery import api

# Create persistence layer
persistence = RecoveryPersistence(Path("/var/realtimex/recovery"))

# Create manager with custom policy
policy = RecoveryPolicy(max_retained_checkpoints=10)
manager = RecoveryManager(
    persistence=persistence,
    event_bus=event_bus,
    policy=policy,
)

# Register callbacks to inject recovered state
def inject_tasks(tasks_data):
    task_system.restore(tasks_data)

def inject_workflows(workflows_data):
    workflow_engine.restore(workflows_data)

manager.register_task_restorer(inject_tasks)
manager.register_workflow_restorer(inject_workflows)

# Initialize global API
api.initialize_api(manager)
```

## Usage Examples

### Creating Checkpoints

```python
from recovery import api

# Collect current state
tasks = task_system.get_all_tasks()
workflows = workflow_engine.get_all_workflows()
memories = memory_system.get_all_references()

# Create checkpoint
api.create_checkpoint(
    checkpoint_id="cp-001",
    tasks=tasks,
    workflows=workflows,
    memories=memories,
    kernel_metadata={"version": "1.0.0"},
    pending_events=event_queue.peek_all(),
)
```

### Recovering from Checkpoints

```python
from recovery import api

# Recover from latest checkpoint
report = api.recover()

# Check results
if report.is_successful:
    print("Recovery completed successfully")
    print(f"Restored {report.items_restored} items")
else:
    print(f"Recovery had {report.items_failed} failures")
    for action in report.suggested_actions:
        print(f"  TODO: {action}")

# Check warnings
for warning in report.warnings:
    logger.warning(warning)
```

### Creating Full Snapshots

```python
from recovery import api

# Capture entire system state
snapshot_data = api.create_snapshot(
    snapshot_id="snap-001",
    config=kernel_config,
    tasks=task_system.get_all_tasks(),
    workflows=workflow_engine.get_all_workflows(),
    memories=memory_system.get_all_references(),
    permissions=permission_cache.to_dict(),
    module_metadata=module_registry.to_dict(),
)
```

### Checking Recovery Status

```python
from recovery import api

status = api.status()
print(f"Checkpoints on disk: {status['total_checkpoints']}")
print(f"Latest recovery: {status['last_recovery_timestamp']}")
print(f"Recovery strategy: {status['strategy']}")
print(f"Checkpoints: {status['checkpoints']}")
print(f"Snapshots: {status['snapshots']}")
```

### Validating Data

```python
from recovery import api

# Validate checkpoint data without recovery
outcome = api.validate(checkpoint_data)
print(f"Warnings: {outcome['warnings']}")
print(f"Clean tasks: {len(outcome['clean']['tasks'])}")
print(f"Isolated tasks: {len(outcome['isolated']['tasks'])}")
```

## Data Restoration Callbacks

The Recovery System uses callbacks to inject restored state back into subsystems.

### Task Restorer

```python
def task_restorer(task_dict: dict[str, Any]) -> None:
    """Inject recovered task into Task System."""
    task = Task.from_checkpoint(task_dict)
    task_system.register(task)

manager.register_task_restorer(task_restorer)
```

### Workflow Restorer

```python
def workflow_restorer(workflow_dict: dict[str, Any]) -> None:
    """Inject recovered workflow into Workflow Engine."""
    workflow = Workflow.from_checkpoint(workflow_dict)
    workflow_engine.register(workflow)

manager.register_workflow_restorer(workflow_restorer)
```

### Memory Restorer

```python
def memory_restorer(memory_dict: dict[str, Any]) -> None:
    """Inject recovered memory reference into Memory System."""
    memory_system.restore_reference(memory_dict)

manager.register_memory_restorer(memory_restorer)
```

## Checkpoint Format

Example checkpoint JSON:

```json
{
  "checkpoint_id": "cp-001",
  "timestamp": "2026-07-18T12:00:00+05:30",
  "tasks": [
    {
      "task_id": "t-123",
      "status": "active",
      "action": "process_request",
      "progress": 45
    }
  ],
  "workflows": [
    {
      "workflow_id": "wf-456",
      "status": "active",
      "steps": [...]
    }
  ],
  "memories": [
    {
      "memory_id": "m-789",
      "scope": "global"
    }
  ],
  "kernel_metadata": {
    "version": "1.0.0",
    "boot_time": "2026-07-18T11:00:00+05:30"
  },
  "pending_events": [...]
}
```

## Recovery Policies

### Retention Management

**Checkpoint Retention:**
- Default: Keep 5 most recent checkpoints
- Oldest checkpoints automatically deleted
- Configurable via `max_retained_checkpoints`

**Snapshot Retention:**
- Default: Keep 10 most recent snapshots
- Simple count-based pruning
- Configurable by modifying snapshot manager

### Checkpoint Frequency

- Default: 60 seconds
- Configurable via `checkpoint_interval_seconds`
- Should align with system needs and disk I/O capacity

## Error Handling

### Recovery Errors

```python
from recovery.exceptions import (
    RecoveryError,
    CheckpointError,
    SnapshotError,
    StateValidationError,
    RecoveryPlannerError,
)

try:
    report = api.recover()
except RecoveryPlannerError as e:
    # Recovery strategy violation (strict mode)
    logger.error(f"Recovery aborted: {e}")
except CheckpointError as e:
    # Checkpoint file issue
    logger.error(f"Checkpoint problem: {e}")
except RecoveryError as e:
    # General recovery failure
    logger.error(f"Recovery failed: {e}")
```

### Validation Failures

Validation failures **do not crash recovery** under fail-safe strategy:

```python
outcome = api.validate(data)
if outcome['warnings']:
    for warning in outcome['warnings']:
        logger.warning(f"Validation issue: {warning}")
    
    # Isolated items are in outcome['isolated']
    isolated_count = (
        len(outcome['isolated']['tasks']) +
        len(outcome['isolated']['workflows']) +
        len(outcome['isolated']['memories'])
    )
    logger.warning(f"{isolated_count} items isolated due to corruption")
```

## Thread Safety

All Recovery System managers use `threading.RLock()` for thread-safe operations:

- `RecoveryManager` - Main orchestrator
- `CheckpointManager` - Checkpoint operations
- `SnapshotManager` - Snapshot operations

This allows concurrent calls to recovery APIs from multiple threads.

## Storage Independence

The Recovery System is storage-independent:

- **Default:** JSON files on local filesystem (`RecoveryPersistence`)
- **Custom:** Implement your own persistence layer by:
  1. Implementing `RecoveryPersistence` interface
  2. Providing `save_checkpoint()`, `load_checkpoint()`, etc.
  3. Passing custom instance to `RecoveryManager`

## Best Practices

1. **Create Checkpoints Regularly**
   - On successful task completion
   - Before major operations
   - Periodically (e.g., every minute)

2. **Monitor Recovery Status**
   - Check `api.status()` during operations
   - Review recovery reports
   - Act on suggested actions

3. **Test Recovery Procedures**
   - Simulate failures in development
   - Verify checkpoint restoration works
   - Test both strategies (fail-safe, strict)

4. **Manage Retention**
   - Set `max_retained_checkpoints` based on disk space
   - Monitor disk usage
   - Archive old snapshots if needed

5. **Handle Isolated Items**
   - Review warnings in recovery reports
   - Re-submit isolated tasks/workflows
   - Investigate root causes of corruption

6. **Use Fail-Safe for Production**
   - Defaults to `fail_safe` strategy
   - Allows system to recover despite minor corruption
   - Provides detailed diagnostics

7. **Use Strict for Critical Systems**
   - Set strategy to `strict` if data integrity is paramount
   - Fail fast on any corruption
   - Requires manual intervention

## Integration with Kernel

### Boot Sequence

```python
# In kernel.py boot()
recovery_manager = RecoveryManager(persistence, event_bus, policy)
recovery_manager.register_task_restorer(inject_tasks)
recovery_manager.register_workflow_restorer(inject_workflows)
api.initialize_api(recovery_manager)

# Perform recovery
recovery_report = api.recover()
if not recovery_report.is_successful:
    logger.warning("Recovery had issues: %s", recovery_report.warnings)
    for action in recovery_report.suggested_actions:
        logger.warning("Suggested: %s", action)
```

### Periodic Checkpointing

```python
# In kernel's main loop or via scheduler
def checkpoint_task():
    api.create_checkpoint(
        checkpoint_id=f"cp-{datetime.now().timestamp()}",
        tasks=task_system.get_all_tasks(),
        workflows=workflow_engine.get_all_workflows(),
        memories=memory_system.get_all_references(),
    )

# Schedule every 60 seconds
scheduler.schedule_recurring(checkpoint_task, interval=60)
```

## Performance Considerations

- **Checkpoint Size**: Grows with number of tasks/workflows
- **Checkpoint Frequency**: Balance between recovery window and disk I/O
- **Retention Limits**: Keep 5-10 checkpoints to manage disk usage
- **File Format**: JSON for readability and debugging (consider binary format if size is issue)

## Debugging

### Enable Debug Logging

```python
import logging

logger = logging.getLogger("realtimex.recovery")
logger.setLevel(logging.DEBUG)
```

### Inspect Checkpoint Files

Checkpoints are JSON files in `recovery/checkpoints/`:

```bash
$ cat recovery/checkpoints/cp-001.json | python3 -m json.tool
```

### Monitor Events

Subscribe to recovery events:

```python
def on_recovery_event(event):
    print(f"Recovery: {event.name}")
    print(f"  Payload: {event.payload}")

event_bus.subscribe("RecoveryStarted", on_recovery_event)
event_bus.subscribe("RecoveryCompleted", on_recovery_event)
event_bus.subscribe("RecoveryFailed", on_recovery_event)
```

## Limitations and Future Improvements

### Current Limitations

1. **Time-Based Snapshot Retention**: Currently count-based, not time-based
2. **No Incremental Checkpoints**: Full checkpoints each time
3. **Simple Isolation**: Corrupted items dropped, not analyzed further

### Future Enhancements

1. **Differential Checkpoints**: Only save changed state
2. **Compression**: Reduce checkpoint file sizes
3. **Remote Backups**: Cloud storage support
4. **Recovery Analytics**: Detailed corruption pattern analysis
5. **Corruption Detection**: Proactive issue detection
6. **Checkpoint Verification**: Periodic validation of stored checkpoints

## Testing

Run the test suite:

```bash
python3 -m unittest specs.test_recovery -v
```

Test cases verify:

- Checkpoint creation and pruning
- Snapshot creation and restoration
- Fail-safe strategy behavior
- Strict strategy behavior
- API facade functionality

## Related Documentation

- **Kernel Architecture**: See `kernel/README.md`
- **Event System**: See `events/README.md`
- **Task System**: See `tasks/README.md`
- **Workflow Engine**: See `workflow/README.md`
- **Memory System**: See `memory/README.md`

"""
Worker lifecycle states and transition validations.
"""

from __future__ import annotations

from enum import Enum

from workers.exceptions import InvalidWorkerLifecycleError


class WorkerState(str, Enum):
    """
    State lifecycle transitions of a Realtimex Worker.
    """
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    IDLE = "IDLE"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    REPORTING = "REPORTING"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    TERMINATED = "TERMINATED"


# Valid state transitions: current_state -> set of next_states
VALID_WORKER_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
    WorkerState.OFFLINE: {
        WorkerState.STARTING,
    },
    WorkerState.STARTING: {
        WorkerState.IDLE,
        WorkerState.TERMINATED,
    },
    WorkerState.IDLE: {
        WorkerState.ASSIGNED,
        WorkerState.TERMINATED,
    },
    WorkerState.ASSIGNED: {
        WorkerState.RUNNING,
        WorkerState.TERMINATED,
        WorkerState.IDLE,
    },
    WorkerState.RUNNING: {
        WorkerState.REPORTING,
        WorkerState.FAILED,
        WorkerState.TERMINATED,
    },
    WorkerState.REPORTING: {
        WorkerState.IDLE,
        WorkerState.TERMINATED,
    },
    WorkerState.FAILED: {
        WorkerState.RECOVERING,
        WorkerState.TERMINATED,
    },
    WorkerState.RECOVERING: {
        WorkerState.IDLE,
        WorkerState.TERMINATED,
    },
    WorkerState.TERMINATED: set(),
}


def validate_worker_transition(current: WorkerState, target: WorkerState) -> None:
    """
    Validate transition between worker states.

    Raises:
        InvalidWorkerLifecycleError: If transition is illegal.
    """
    if current == target:
        return
    allowed = VALID_WORKER_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidWorkerLifecycleError(
            f"Invalid worker state transition from '{current.value}' to '{target.value}'."
        )

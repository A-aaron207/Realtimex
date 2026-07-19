"""
Task state definitions and transition validation for the Realtimex Task System.
"""

from __future__ import annotations

from enum import Enum
from typing import Set

from tasks.exceptions import InvalidTaskStateTransitionError


class TaskState(str, Enum):
    """
    Lifecycle states of a Realtimex Task.
    """
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_PERMISSION = "WAITING_FOR_PERMISSION"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Valid state transitions mapping: current_state -> set of next_states
VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {
        TaskState.PLANNING,
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.CANCELLED,
    },
    TaskState.PLANNING: {
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.QUEUED: {
        TaskState.RUNNING,
        TaskState.CANCELLED,
    },
    TaskState.RUNNING: {
        TaskState.PAUSED,
        TaskState.WAITING_FOR_PERMISSION,
        TaskState.WAITING_FOR_USER,
        TaskState.RETRYING,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.PAUSED: {
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.CANCELLED,
    },
    TaskState.WAITING_FOR_PERMISSION: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.WAITING_FOR_USER: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.RETRYING: {
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


def validate_transition(current: TaskState, target: TaskState) -> None:
    """
    Validate a state transition.

    Args:
        current: The current task state.
        target: The target task state.

    Raises:
        InvalidTaskStateTransitionError: If the transition is not allowed.
    """
    if current == target:
        return

    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTaskStateTransitionError(
            f"Invalid transition from state '{current.value}' to '{target.value}'."
        )


def is_terminal_state(state: TaskState) -> bool:
    """
    Check if the state is terminal (no transitions allowed out of it).
    """
    return state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

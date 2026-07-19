"""
Realtimex Tasks package.

Provides the production-quality Task System that is the central state
container of the Realtimex Kernel.

Components:
    - Task: durable, immutable representation of work.
    - TaskPriority: execution priority levels (LOW, NORMAL, HIGH, CRITICAL).
    - TaskState: lifecycle states (CREATED -> ... -> COMPLETED/FAILED/CANCELLED).
    - TaskHistoryEntry: entry tracking events within a single task's lifetime.
    - TaskManager: coordinates creation, states, and event notifications.
    - TaskRepository: thread-safe cache and storage mediator.
    - TaskPersistence: disk-based JSON persistence.
    - TaskRecovery: checks and restores incomplete tasks on startup.
    - TaskAPI: query and search interface.
"""

from tasks.api import TaskAPI  # noqa: F401
from tasks.exceptions import (  # noqa: F401
    InvalidTaskStateTransitionError,
    TaskNotFoundError,
    TaskPersistenceError,
    TaskRecoveryError,
    TaskSystemError,
    TaskValidationError,
)
from tasks.history import add_history_entry  # noqa: F401
from tasks.manager import TaskManager  # noqa: F401
from tasks.persistence import TaskPersistence  # noqa: F401
from tasks.recovery import TaskRecovery  # noqa: F401
from tasks.repository import TaskRepository  # noqa: F401
from tasks.states import TaskState, is_terminal_state  # noqa: F401
from tasks.task import Task, TaskHistoryEntry, TaskPriority  # noqa: F401

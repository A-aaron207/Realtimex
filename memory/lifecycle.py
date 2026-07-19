"""
Memory lifecycle states and state transition validation in the Realtimex Memory System.
"""

from __future__ import annotations

from memory.exceptions import MemoryValidationError
from memory.registry import MemoryStatus

# Valid status transitions: current -> allowed targets
VALID_LIFECYCLE_TRANSITIONS: dict[MemoryStatus, set[MemoryStatus]] = {
    "created": {"active", "archived", "deleted"},
    "active": {"archived", "deleted"},
    "archived": {"active", "deleted"},
    "deleted": set(),
}


def validate_lifecycle_transition(current: MemoryStatus, target: MemoryStatus) -> None:
    """
    Validate if transitioning from current state to target state is allowed.

    Raises:
        MemoryValidationError: If the lifecycle transition is illegal.
    """
    if current == target:
        return

    allowed = VALID_LIFECYCLE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise MemoryValidationError(
            f"Invalid memory lifecycle state transition: cannot transition from '{current}' to '{target}'."
        )

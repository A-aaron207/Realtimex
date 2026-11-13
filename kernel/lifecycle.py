"""
Kernel lifecycle state definitions.

The Kernel moves through a strict, linear sequence of states from the
moment the process starts to the moment it terminates. This module
defines that state space as an Enum so that any component can query
or reason about the Kernel's current phase.
"""

from __future__ import annotations

import threading
from enum import Enum


class KernelState(Enum):
    """
    The set of states a Kernel instance can occupy over its lifetime.

    Transitions proceed in the following order:

        OFFLINE -> BOOTING -> INITIALIZING -> READY -> RUNNING
        -> SHUTTING_DOWN -> OFFLINE
    """

    OFFLINE = "OFFLINE"
    BOOTING = "BOOTING"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    RUNNING = "RUNNING"
    SHUTTING_DOWN = "SHUTTING_DOWN"

    def __str__(self) -> str:
        return self.value


class InvalidStateTransition(Exception):
    """Raised when the Kernel attempts an illegal lifecycle state transition."""

    def __init__(self, current: KernelState, attempted: KernelState) -> None:
        self.current = current
        self.attempted = attempted
        super().__init__(
            f"Cannot transition Kernel from {current} to {attempted}: "
            f"not an allowed lifecycle transition."
        )


class LifecycleManager:
    """
    Enforces valid Kernel state transitions.

    Responsibilities:
        - Hold the Kernel's current lifecycle state.
        - Validate and apply state transitions according to the
          allowed lifecycle graph.
    """

    _ALLOWED_TRANSITIONS: dict[KernelState, tuple[KernelState, ...]] = {
        KernelState.OFFLINE: (KernelState.BOOTING,),
        KernelState.BOOTING: (KernelState.INITIALIZING,),
        KernelState.INITIALIZING: (KernelState.READY,),
        KernelState.READY: (KernelState.RUNNING,),
        KernelState.RUNNING: (KernelState.SHUTTING_DOWN,),
        KernelState.SHUTTING_DOWN: (KernelState.OFFLINE,),
    }

    def __init__(self, initial_state: KernelState = KernelState.OFFLINE) -> None:
        """
        Initialize the lifecycle manager.

        Args:
            initial_state: The state the Kernel begins in. Defaults to OFFLINE.
        """
        self._state = initial_state
        self._lock = threading.RLock()

    @property
    def state(self) -> KernelState:
        """The Kernel's current lifecycle state."""
        with self._lock:
            return self._state

    def transition_to(self, new_state: KernelState) -> None:
        """
        Move the Kernel to a new lifecycle state.

        Args:
            new_state: The state to transition into.

        Raises:
            InvalidStateTransition: If the transition is not permitted
                from the current state.
        """
        with self._lock:
            allowed = self._ALLOWED_TRANSITIONS.get(self._state, ())
            if new_state not in allowed:
                raise InvalidStateTransition(current=self._state, attempted=new_state)
            self._state = new_state


"""
Unit tests for the Kernel Lifecycle Manager.
"""

from __future__ import annotations

import pytest

from kernel.lifecycle import (
    KernelState,
    LifecycleManager,
    InvalidStateTransition,
)


def test_initial_state() -> None:
    """Verify the default initial state is OFFLINE."""
    manager = LifecycleManager()
    assert manager.state == KernelState.OFFLINE


def test_custom_initial_state() -> None:
    """Verify that a custom initial state can be set."""
    manager = LifecycleManager(initial_state=KernelState.READY)
    assert manager.state == KernelState.READY


def test_valid_state_transitions() -> None:
    """Verify the linear sequence of valid transitions."""
    manager = LifecycleManager()

    # OFFLINE -> BOOTING
    manager.transition_to(KernelState.BOOTING)
    assert manager.state == KernelState.BOOTING

    # BOOTING -> INITIALIZING
    manager.transition_to(KernelState.INITIALIZING)
    assert manager.state == KernelState.INITIALIZING

    # INITIALIZING -> READY
    manager.transition_to(KernelState.READY)
    assert manager.state == KernelState.READY

    # READY -> RUNNING
    manager.transition_to(KernelState.RUNNING)
    assert manager.state == KernelState.RUNNING

    # RUNNING -> SHUTTING_DOWN
    manager.transition_to(KernelState.SHUTTING_DOWN)
    assert manager.state == KernelState.SHUTTING_DOWN

    # SHUTTING_DOWN -> OFFLINE
    manager.transition_to(KernelState.OFFLINE)
    assert manager.state == KernelState.OFFLINE


def test_invalid_state_transitions() -> None:
    """Verify that invalid state transitions raise InvalidStateTransition."""
    manager = LifecycleManager()

    # Current state is OFFLINE: allowed transition is BOOTING
    # Attempting transition to other states should fail
    for invalid_state in [
        KernelState.INITIALIZING,
        KernelState.READY,
        KernelState.RUNNING,
        KernelState.SHUTTING_DOWN,
        KernelState.OFFLINE,
    ]:
        with pytest.raises(InvalidStateTransition) as exc_info:
            manager.transition_to(invalid_state)
        assert exc_info.value.current == KernelState.OFFLINE
        assert exc_info.value.attempted == invalid_state

    # Move to BOOTING: allowed transition is INITIALIZING
    manager.transition_to(KernelState.BOOTING)
    with pytest.raises(InvalidStateTransition):
        manager.transition_to(KernelState.READY)

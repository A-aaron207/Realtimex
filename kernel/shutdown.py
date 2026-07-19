"""
Kernel shutdown sequence.

Mirrors the boot sequence's philosophy: shutdown is a small, ordered
set of steps, each its own function, each emitting an event. For
Milestone 1 there are no services or workers to drain, so this is a
minimal but structurally complete implementation that later
milestones will extend (e.g. draining workers, flushing memory,
persisting state).
"""

from __future__ import annotations

import logging

from events.event import Event
from events.event_bus import EventBus
from events.event_types import KernelEventType


def emit_shutdown_started(event_bus: EventBus, logger: logging.Logger) -> None:
    """
    Shutdown step: announce that shutdown has begun.

    Args:
        event_bus: The Kernel's Event Bus.
        logger: The Kernel logger.
    """
    logger.info("Kernel shutdown started.")
    event_bus.emit(Event(name=KernelEventType.KERNEL_SHUTDOWN_STARTED, source="kernel.shutdown"))


def emit_shutdown_complete(event_bus: EventBus, logger: logging.Logger) -> None:
    """
    Shutdown step: announce that shutdown has completed.

    Args:
        event_bus: The Kernel's Event Bus.
        logger: The Kernel logger.
    """
    logger.info("Kernel shutdown complete.")
    event_bus.emit(Event(name=KernelEventType.KERNEL_SHUTDOWN_COMPLETE, source="kernel.shutdown"))


def run_shutdown_sequence(event_bus: EventBus, logger: logging.Logger) -> None:
    """
    Execute the full Kernel shutdown sequence in order.

    Args:
        event_bus: The Kernel's Event Bus.
        logger: The Kernel logger.
    """
    emit_shutdown_started(event_bus, logger)
    emit_shutdown_complete(event_bus, logger)

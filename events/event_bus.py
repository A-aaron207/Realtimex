"""
Backwards-compatibility shim for the original ``events.event_bus`` import path.

Milestone 1/2 code imports ``EventBus`` from ``events.event_bus``.  Now
that the production Event Bus lives in ``events.bus``, this module
re-exports the class so every existing import continues to resolve.
"""

from __future__ import annotations

from events.bus import EventBus, EventHandler  # noqa: F401

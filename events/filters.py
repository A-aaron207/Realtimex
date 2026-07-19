"""
Event filtering capabilities for the Event System.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any

from events.event import Event, EventPriority

@dataclass(frozen=True)
class EventFilter:
    """Immutable filter specification for event matching."""
    event_types: frozenset[str] = frozenset()
    sources: frozenset[str] = frozenset()
    priorities: frozenset[EventPriority] = frozenset()
    task_ids: frozenset[str] = frozenset()
    wildcard_patterns: tuple[str, ...] = ()

    def matches(self, event: Event) -> bool:
        """Check if an event matches this filter."""
        if self.event_types or self.wildcard_patterns:
            type_match = False
            if self.event_types and event.name in self.event_types:
                type_match = True
            elif self.wildcard_patterns:
                for pattern in self.wildcard_patterns:
                    if fnmatch.fnmatch(event.name, pattern):
                        type_match = True
                        break
            if not type_match:
                return False

        if self.sources and event.source not in self.sources:
            return False
            
        if self.priorities and event.priority not in self.priorities:
            return False
            
        if self.task_ids and event.task_id not in self.task_ids:
            return False
            
        return True

    @staticmethod
    def match_all() -> EventFilter:
        """Filter that matches every event."""
        return EventFilter()

    @staticmethod
    def for_event_types(*event_types: str) -> EventFilter:
        """Filter that matches specific event types."""
        return EventFilter(event_types=frozenset(event_types))

    @staticmethod
    def for_sources(*sources: str) -> EventFilter:
        """Filter that matches specific sources."""
        return EventFilter(sources=frozenset(sources))

    @staticmethod
    def for_priority_at_least(priority: EventPriority) -> EventFilter:
        """Filter that matches events with a priority greater than or equal to the given priority."""
        valid_priorities = frozenset(p for p in EventPriority if p >= priority)
        return EventFilter(priorities=valid_priorities)

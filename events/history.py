"""
In-memory event history management.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from typing import Any, Optional

from events.event import Event
from events.filters import EventFilter


class EventHistory:
    """Thread-safe, bounded, in-memory event history."""
    
    DEFAULT_MAX_SIZE = 10_000
    
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self._events: deque[Event] = deque(maxlen=max_size)
        self._max_size = max_size
        self._lock = threading.RLock()
    
    def record(self, event: Event) -> None:
        """Add an event to history."""
        with self._lock:
            self._events.append(event)
    
    def recent_events(self, count: int = 50) -> list[Event]:
        """Return the N most recent events, newest first."""
        with self._lock:
            # Events are appended to the right, so the newest are at the right end
            events = list(self._events)[-count:]
            return list(reversed(events))
    
    def find(self, event_id: str) -> Event | None:
        """Find a specific event by its event_id."""
        with self._lock:
            for event in reversed(self._events):
                if event.event_id == event_id:
                    return event
        return None
    
    def filter(self, *, event_filter: EventFilter | None = None,
               event_type: str | None = None,
               source: str | None = None,
               task_id: str | None = None,
               since: datetime | None = None,
               until: datetime | None = None,
               limit: int = 100) -> list[Event]:
        """Filter events by various criteria. Returns newest first."""
        if event_filter is None:
            # Build an EventFilter from the convenience kwargs if event_filter not provided
            event_filter = EventFilter(
                event_types=frozenset({event_type}) if event_type else frozenset(),
                sources=frozenset({source}) if source else frozenset(),
                task_ids=frozenset({task_id}) if task_id else frozenset(),
            )
            
        filtered_events = []
        with self._lock:
            # Iterate backwards to get newest first
            for event in reversed(self._events):
                if len(filtered_events) >= limit:
                    break
                    
                # Apply time-range filtering separately
                if since is not None and event.timestamp < since:
                    continue
                if until is not None and event.timestamp > until:
                    continue
                    
                if event_filter.matches(event):
                    filtered_events.append(event)
                    
        return filtered_events
    
    def all_events(self) -> list[Event]:
        """Return all events in history, oldest first."""
        with self._lock:
            return list(self._events)
    
    def clear(self) -> None:
        """Clear all events from history."""
        with self._lock:
            self._events.clear()
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
    
    @property
    def max_size(self) -> int:
        return self._max_size

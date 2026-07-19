"""
Event replay system for debugging, auditing, and recovery.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from events.event import Event
from events.filters import EventFilter
from events.persistence import EventPersistence
from events.exceptions import EventReplayError


class EventReplay:
    """Replays persisted events through the event bus for debugging, auditing, and recovery."""
    
    def __init__(self, persistence: EventPersistence) -> None:
        self._persistence = persistence
        self._logger = logging.getLogger("realtimex.events.replay")
    
    def replay(self, handler: Callable[[Event], None]) -> int:
        """Replay all persisted events through the handler in chronological order.
        Returns the number of events replayed."""
        events = self._persistence.load_all()
        return self._replay_events(events, handler)
    
    def replay_until(self, handler: Callable[[Event], None], timestamp: datetime) -> int:
        """Replay events up to and including the given timestamp.
        Returns the number of events replayed."""
        events = self._persistence.load_all()
        filtered = [e for e in events if e.timestamp <= timestamp]
        return self._replay_events(filtered, handler)
    
    def replay_task(self, handler: Callable[[Event], None], task_id: str) -> int:
        """Replay all events for a specific task.
        Returns the number of events replayed."""
        events = self._persistence.load_for_task(task_id)
        return self._replay_events(events, handler)
    
    def replay_filtered(self, handler: Callable[[Event], None], event_filter: EventFilter) -> int:
        """Replay events matching a filter.
        Returns the number of events replayed."""
        events = self._persistence.load_all()
        filtered = [e for e in events if event_filter.matches(e)]
        return self._replay_events(filtered, handler)
    
    def _replay_events(self, events: list[Event], handler: Callable[[Event], None]) -> int:
        """Internal: replay a list of events through the handler, catching errors."""
        events.sort(key=lambda e: e.timestamp)
        count = 0
        for event in events:
            try:
                handler(event)
                count += 1
            except Exception as e:
                self._logger.error(f"Error replaying event {event.event_id}: {e}")
        return count

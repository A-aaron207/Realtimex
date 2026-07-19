"""
Subscriber and Registry system for event handlers.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Any

from events.event import Event
from events.filters import EventFilter

EventHandler = Callable[[Event], None]

@dataclass
class Subscriber:
    """A registered event subscriber."""
    subscriber_id: str
    handler: EventHandler
    filter: EventFilter
    source_name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    
    def should_receive(self, event: Event) -> bool:
        """Determine if the subscriber should receive the given event."""
        return self.active and self.filter.matches(event)
    
    def deliver(self, event: Event) -> None:
        """Deliver the event to the subscriber's handler."""
        self.handler(event)

class SubscriberRegistry:
    """Thread-safe registry of event subscribers."""
    
    def __init__(self) -> None:
        self._subscribers: dict[str, Subscriber] = {}
        self._lock = threading.RLock()
    
    def register(self, handler: EventHandler, filter: EventFilter, source_name: str = "") -> Subscriber:
        """Register a new subscriber. Returns the Subscriber object."""
        with self._lock:
            subscriber_id = str(uuid.uuid4())
            subscriber = Subscriber(
                subscriber_id=subscriber_id,
                handler=handler,
                filter=filter,
                source_name=source_name
            )
            self._subscribers[subscriber_id] = subscriber
            return subscriber
    
    def unregister(self, subscriber_id: str) -> bool:
        """Remove a subscriber by ID. Returns True if found and removed."""
        with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                return True
            return False
    
    def unregister_by_handler(self, handler: EventHandler) -> int:
        """Remove all subscribers using the given handler. Returns count removed."""
        with self._lock:
            to_remove = [
                sub_id for sub_id, sub in self._subscribers.items()
                if sub.handler == handler
            ]
            for sub_id in to_remove:
                del self._subscribers[sub_id]
            return len(to_remove)
    
    def get_matching_subscribers(self, event: Event) -> list[Subscriber]:
        """Return all subscribers that should receive this event, sorted by registration order."""
        with self._lock:
            return [
                sub for sub in self._subscribers.values()
                if sub.should_receive(event)
            ]
    
    def list_subscribers(self) -> list[Subscriber]:
        """List all registered subscribers."""
        with self._lock:
            return list(self._subscribers.values())
    
    def clear(self) -> None:
        """Clear all subscribers from the registry."""
        with self._lock:
            self._subscribers.clear()
    
    def count(self) -> int:
        """Return the number of registered subscribers."""
        with self._lock:
            return len(self._subscribers)

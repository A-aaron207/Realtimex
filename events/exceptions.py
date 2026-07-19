"""
Exception hierarchy for the Realtimex Event System.
"""
from __future__ import annotations

class EventSystemError(Exception):
    """Base exception for all event system errors."""
    pass

class EventValidationError(EventSystemError):
    """Raised when event data is invalid."""
    pass

class EventDispatchError(EventSystemError):
    """Raised when an event fails to dispatch."""
    pass

class EventPersistenceError(EventSystemError):
    """Raised for event persistence I/O errors."""
    pass

class EventReplayError(EventSystemError):
    """Raised when event replay fails."""
    pass

class SubscriberError(EventSystemError):
    """Raised for subscriber registration or execution errors."""
    pass

class EventBusShutdownError(EventSystemError):
    """Raised when operations are attempted on a shut-down event bus."""
    pass

"""
Realtimex Events package.

Provides the production-quality Event System that is the communication
backbone of the Realtimex Kernel.  Every subsystem publishes and
subscribes to events through this infrastructure.

Components:
    - Event: immutable record of something that happened.
    - EventPriority: dispatch priority levels (LOW, NORMAL, HIGH, CRITICAL).
    - EventBus: async pub/sub hub with priority-aware dispatch.
    - EventManager: top-level façade that wires all components together.
    - EventHistory: bounded in-memory event history.
    - EventLogger: structured JSONL event logging.
    - EventPersistence: durable JSONL event storage.
    - EventReplay: replay persisted events for debugging/recovery.
    - EventFilter: rich event matching for subscribers.
    - Subscriber / SubscriberRegistry: subscriber management.
    - Event type constants: KernelEventType, ModuleEventType, EventSystemEventType, TaskEventType, WorkerEventType, SchedulerEventType.
"""

from events.bus import EventBus  # noqa: F401
from events.event import Event, EventPriority  # noqa: F401
from events.event_types import (  # noqa: F401
    EventSystemEventType,
    KernelEventType,
    ModuleEventType,
    TaskEventType,
    WorkerEventType,
    SchedulerEventType,
)
from events.exceptions import (  # noqa: F401
    EventBusShutdownError,
    EventDispatchError,
    EventPersistenceError,
    EventReplayError,
    EventSystemError,
    EventValidationError,
    SubscriberError,
)
from events.filters import EventFilter  # noqa: F401
from events.history import EventHistory  # noqa: F401
from events.logger import EventLogger  # noqa: F401
from events.manager import EventManager  # noqa: F401
from events.persistence import EventPersistence  # noqa: F401
from events.replay import EventReplay  # noqa: F401
from events.subscriber import Subscriber, SubscriberRegistry  # noqa: F401

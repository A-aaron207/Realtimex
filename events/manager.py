"""
Event Manager — top-level orchestrator of the Realtimex Event System.

The Event Manager is the single entry point that assembles every event-
system component (Event Bus, Event History, Event Logger, Event
Persistence, Event Replay) and exposes a unified API to the rest of the
Kernel.

During the boot sequence the Kernel constructs an ``EventManager``
instead of a bare ``EventBus``.  The manager wires the components
together and returns them in a ready-to-use state.

Design goals:
    - One-stop shop: callers never need to know about the internal
      wiring of bus -> history -> persistence -> replay.
    - Backwards compatible: the manager exposes ``.event_bus`` so that
      existing code that calls ``bus.emit()`` continues to work.
    - Production ready: all components are thread-safe and start
      cleanly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from events.bus import EventBus
from events.event import Event, EventPriority
from events.event_types import EventSystemEventType
from events.filters import EventFilter
from events.history import EventHistory
from events.logger import EventLogger
from events.persistence import EventPersistence
from events.replay import EventReplay
from events.subscriber import Subscriber


class EventManager:
    """
    Façade that owns and coordinates every Event System component.

    Components managed:
        - :class:`EventBus`: publish/subscribe/dispatch
        - :class:`EventHistory`: bounded in-memory history
        - :class:`EventLogger`: structured JSONL event logging
        - :class:`EventPersistence`: durable JSONL event storage
        - :class:`EventReplay`: replay persisted events

    Public API
    ----------
    publish(event)
        Publish an event through the bus.

    emit(event)
        Alias for publish (backwards compat).

    subscribe(event_type, listener)
        Simple subscription by event name.

    subscribe_with_filter(handler, filter, source_name)
        Rich filtered subscription.

    unsubscribe(listener)
        Remove all subscriptions for a handler.

    recent_events(count)
        Return the N most recent events.

    find_event(event_id)
        Look up an event by ID.

    filter_events(...)
        Query event history.

    replay(handler)
        Replay all persisted events through a handler.

    replay_until(handler, timestamp)
        Replay events up to a timestamp.

    replay_task(handler, task_id)
        Replay events for a specific task.

    shutdown()
        Gracefully stop the Event Bus and flush pending work.
    """

    def __init__(
        self,
        logger: logging.Logger,
        log_directory: Path,
        *,
        history_max_size: int = EventHistory.DEFAULT_MAX_SIZE,
        persistence_filename: str = EventPersistence.DEFAULT_FILENAME,
        event_log_filename: str = EventLogger.DEFAULT_FILENAME,
        auto_start: bool = True,
    ) -> None:
        """
        Initialize the Event Manager and all its components.

        Args:
            logger: The Kernel logger for diagnostic output.
            log_directory: Directory where event logs and persistence
                files are written.
            history_max_size: Maximum number of events retained in
                in-memory history before the oldest is evicted.
            persistence_filename: Filename for the durable events file.
            event_log_filename: Filename for the structured event log.
            auto_start: Whether the Event Bus dispatcher starts
                immediately (set ``False`` for testing).
        """
        self._logger = logger

        # --- Component assembly ---
        self._history = EventHistory(max_size=history_max_size)

        self._event_logger = EventLogger(
            log_directory=log_directory,
            filename=event_log_filename,
            console_logger=logger,
        )

        self._persistence = EventPersistence(
            log_directory=log_directory,
            filename=persistence_filename,
        )

        self._replay = EventReplay(persistence=self._persistence)

        self._event_bus = EventBus(
            logger=logger,
            event_history=self._history,
            event_logger=self._event_logger,
            event_persistence=self._persistence,
            auto_start=auto_start,
        )

        self._logger.debug("Event Manager initialized.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Event Bus dispatcher if not already running."""
        self._event_bus.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shut down the Event System.

        Args:
            timeout: Maximum seconds to wait for the dispatcher thread.
        """
        self._event_bus.shutdown(timeout=timeout)
        self._logger.info("Event Manager shut down.")

    @property
    def is_running(self) -> bool:
        """Whether the Event Bus dispatcher is active."""
        return self._event_bus.is_running

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """
        Publish an event through the Event Bus.

        The event is recorded in history, logged, persisted, and then
        dispatched asynchronously to matching subscribers.

        Args:
            event: The event to publish.
        """
        self._event_bus.publish(event)

    def emit(self, event: Event) -> None:
        """Backwards-compatible alias for ``publish()``."""
        self._event_bus.emit(event)

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def subscribe(
        self, event_type: str, listener: Callable[[Event], None]
    ) -> Subscriber:
        """
        Register a listener for a specific event type name.

        Args:
            event_type: The event name to listen for.
            listener: A callable that accepts an Event instance.

        Returns:
            The Subscriber object.
        """
        return self._event_bus.subscribe(event_type, listener)

    def subscribe_with_filter(
        self,
        handler: Callable[[Event], None],
        event_filter: EventFilter,
        source_name: str = "",
    ) -> Subscriber:
        """
        Register a subscriber with a rich event filter.

        Args:
            handler: A callable that accepts an Event instance.
            event_filter: An EventFilter describing which events the
                subscriber should receive.
            source_name: Human-readable name of the subscribing
                component.

        Returns:
            The Subscriber object.
        """
        return self._event_bus.subscribe_with_filter(
            handler=handler,
            event_filter=event_filter,
            source_name=source_name,
        )

    def subscribe_all(
        self,
        handler: Callable[[Event], None],
        source_name: str = "",
    ) -> Subscriber:
        """
        Subscribe a handler to receive **every** event.

        Args:
            handler: A callable that accepts an Event instance.
            source_name: Human-readable name of the subscribing
                component (e.g. ``"Logger"``).

        Returns:
            The Subscriber object.
        """
        return self._event_bus.subscribe_with_filter(
            handler=handler,
            event_filter=EventFilter.match_all(),
            source_name=source_name,
        )

    def unsubscribe(self, listener: Callable[[Event], None]) -> int:
        """
        Remove all subscriptions for a handler.

        Returns:
            The number of subscriptions removed.
        """
        return self._event_bus.unsubscribe(listener)

    # ------------------------------------------------------------------
    # History / query
    # ------------------------------------------------------------------

    def recent_events(self, count: int = 50) -> list[Event]:
        """
        Return the N most recent events, newest first.

        Args:
            count: Number of events to return.
        """
        return self._history.recent_events(count)

    def find_event(self, event_id: str) -> Event | None:
        """
        Look up a specific event by its ID.

        Args:
            event_id: The UUID of the event.
        """
        return self._history.find(event_id)

    def filter_events(
        self,
        *,
        event_filter: EventFilter | None = None,
        event_type: str | None = None,
        source: str | None = None,
        task_id: str | None = None,
        since: Any = None,
        until: Any = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        Query event history with flexible criteria.

        Args:
            event_filter: A pre-built EventFilter (overrides kwargs).
            event_type: Filter by event name.
            source: Filter by source component.
            task_id: Filter by task ID.
            since: Only include events after this datetime.
            until: Only include events before this datetime.
            limit: Maximum number of events to return.

        Returns:
            Matching events, newest first.
        """
        return self._history.filter(
            event_filter=event_filter,
            event_type=event_type,
            source=source,
            task_id=task_id,
            since=since,
            until=until,
            limit=limit,
        )

    def clear_history(self) -> None:
        """Clear all events from in-memory history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(self, handler: Callable[[Event], None]) -> int:
        """
        Replay all persisted events through a handler.

        Args:
            handler: Called once for each replayed event.

        Returns:
            Number of events replayed.
        """
        return self._replay.replay(handler)

    def replay_until(
        self, handler: Callable[[Event], None], timestamp: Any
    ) -> int:
        """
        Replay persisted events up to a timestamp.

        Args:
            handler: Called once for each replayed event.
            timestamp: Stop replay after this datetime.

        Returns:
            Number of events replayed.
        """
        return self._replay.replay_until(handler, timestamp)

    def replay_task(
        self, handler: Callable[[Event], None], task_id: str
    ) -> int:
        """
        Replay all persisted events for a specific task.

        Args:
            handler: Called once for each replayed event.
            task_id: The task to replay events for.

        Returns:
            Number of events replayed.
        """
        return self._replay.replay_task(handler, task_id)

    def replay_filtered(
        self, handler: Callable[[Event], None], event_filter: EventFilter
    ) -> int:
        """
        Replay persisted events matching a filter.

        Args:
            handler: Called once for each replayed event.
            event_filter: Only events matching this filter are replayed.

        Returns:
            Number of events replayed.
        """
        return self._replay.replay_filtered(handler, event_filter)

    # ------------------------------------------------------------------
    # Component accessors
    # ------------------------------------------------------------------

    @property
    def event_bus(self) -> EventBus:
        """The underlying Event Bus."""
        return self._event_bus

    @property
    def history(self) -> EventHistory:
        """The in-memory event history."""
        return self._history

    @property
    def persistence(self) -> EventPersistence:
        """The event persistence layer."""
        return self._persistence

    @property
    def event_logger(self) -> EventLogger:
        """The structured event logger."""
        return self._event_logger

    @property
    def event_replay(self) -> EventReplay:
        """The event replay system."""
        return self._replay

    @property
    def subscriber_count(self) -> int:
        """Total number of registered subscribers."""
        return self._event_bus.subscriber_count

    @property
    def history_size(self) -> int:
        """Number of events currently in history."""
        return len(self._history)

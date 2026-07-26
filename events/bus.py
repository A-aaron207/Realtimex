"""
Event Bus — the communication backbone of the Realtimex Kernel.

The Event Bus is the central pub/sub hub through which every subsystem
communicates.  It accepts published events, queues them by priority,
and dispatches them to matching subscribers asynchronously in a
dedicated background thread.

Design decisions:
    - A single ``threading.Thread`` processes the priority queue so
      that publishers never block on subscriber execution.
    - A ``queue.PriorityQueue`` ensures CRITICAL events are dispatched
      before LOW events.
    - Subscriber exceptions are caught, logged, and never propagate
      to the dispatcher or the publisher.
    - The bus is fully thread-safe: any number of threads may call
      ``publish()`` concurrently.
    - ``shutdown()`` drains the queue before stopping the dispatcher.

The old ``EventBus`` in ``event_bus.py`` is superseded by this module
but kept for import-path compatibility during the transition.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import TYPE_CHECKING, Callable

from events.event import Event, EventPriority
from events.exceptions import EventBusShutdownError
from events.filters import EventFilter
from events.subscriber import Subscriber, SubscriberRegistry

if TYPE_CHECKING:
    from events.history import EventHistory
    from events.logger import EventLogger
    from events.persistence import EventPersistence

EventHandler = Callable[[Event], None]


class _SentinelEvent:
    """Marker placed on the queue to signal the dispatcher to stop.

    Implements ``__lt__`` so that the sentinel always sorts *after*
    every real ``_PrioritizedEvent`` in the priority queue.
    """

    def __lt__(self, other: object) -> bool:
        return False

    def __gt__(self, other: object) -> bool:
        return True

    def __le__(self, other: object) -> bool:
        return isinstance(other, _SentinelEvent)

    def __ge__(self, other: object) -> bool:
        return True


class _PrioritizedEvent:
    """Wrapper that makes ``Event`` instances comparable by priority
    (higher priority value = dispatched first) and by arrival order
    (FIFO within the same priority)."""

    __slots__ = ("sort_key", "event")

    def __init__(self, event: Event, sequence: int) -> None:
        # PriorityQueue pops the *smallest* item first, so negate
        # the priority value so that CRITICAL (30) beats LOW (0).
        self.sort_key = (-int(event.priority), sequence)
        self.event = event

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, _SentinelEvent):
            return True
        if hasattr(other, "sort_key"):
            return self.sort_key < other.sort_key
        return False


class EventBus:
    """
    Production-quality, thread-safe, priority-aware Event Bus.

    Public API
    ----------
    publish(event)
        Enqueue an event for asynchronous dispatch.

    emit(event)
        Alias for ``publish`` — keeps backwards compatibility with
        existing Milestone 1/2 call sites that use ``bus.emit(...)``.

    subscribe(event_type, listener)
        Register a listener for a specific event type name (simple API
        compatible with Milestone 1).

    subscribe_with_filter(handler, event_filter, source_name)
        Register a subscriber with a rich ``EventFilter`` (full API).

    unsubscribe(listener)
        Remove all subscriptions for a given handler.

    dispatch()
        Manually process all queued events (useful in tests or when
        the background dispatcher is not running).

    shutdown()
        Drain remaining events and stop the background dispatcher.

    history()
        Return a copy of all events emitted since the bus was created.
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        event_history: EventHistory | None = None,
        event_logger: EventLogger | None = None,
        event_persistence: EventPersistence | None = None,
        auto_start: bool = True,
    ) -> None:
        """
        Initialize the Event Bus.

        Args:
            logger: A configured logger for diagnostic output.
            event_history: Optional in-memory event history to record into.
            event_logger: Optional structured event logger (JSONL).
            event_persistence: Optional event persistence layer.
            auto_start: Whether to start the background dispatcher
                immediately.  Set to ``False`` for unit-testing or
                synchronous usage.
        """
        self._logger = logger
        self._subscriber_registry = SubscriberRegistry()
        self._queue: queue.PriorityQueue[_PrioritizedEvent | _SentinelEvent] = (
            queue.PriorityQueue()
        )
        self._sequence = 0
        self._sequence_lock = threading.Lock()

        # Optional infrastructure components
        self._event_history = event_history
        self._event_logger = event_logger
        self._event_persistence = event_persistence

        # Legacy in-memory history for backwards compatibility
        self._legacy_history: list[Event] = []
        self._legacy_history_lock = threading.Lock()

        # Dispatcher thread management
        self._running = False
        self._shutdown_event = threading.Event()
        self._dispatcher_thread: threading.Thread | None = None

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background dispatcher thread."""
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop,
            name="EventBus-Dispatcher",
            daemon=True,
        )
        self._dispatcher_thread.start()
        self._logger.debug("Event Bus dispatcher started.")

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Drain the event queue and stop the background dispatcher.

        Args:
            timeout: Maximum seconds to wait for the dispatcher thread
                to finish after the sentinel is placed.
        """
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()

        # Place a sentinel so the dispatcher thread wakes up and exits.
        self._queue.put(_SentinelEvent())

        if self._dispatcher_thread is not None:
            self._dispatcher_thread.join(timeout=timeout)
            if self._dispatcher_thread.is_alive():
                self._logger.warning(
                    "Event Bus dispatcher did not stop within %.1fs.", timeout
                )
            self._dispatcher_thread = None

        self._logger.info("Event Bus shut down.")

    @property
    def is_running(self) -> bool:
        """Whether the background dispatcher is active."""
        return self._running

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """
        Enqueue an event for asynchronous dispatch to subscribers.

        The event is immediately recorded in history, logged, and
        persisted (if those components are attached), and then placed
        onto the priority queue for background dispatch.

        Args:
            event: The Event to publish.

        Raises:
            EventBusShutdownError: If the bus has been shut down.
        """
        if self._shutdown_event.is_set():
            raise EventBusShutdownError(
                "Cannot publish events after the Event Bus has been shut down."
            )

        # Record in legacy history (backwards compat with bus.history())
        with self._legacy_history_lock:
            self._legacy_history.append(event)

        # Record in structured history
        if self._event_history is not None:
            self._event_history.record(event)

        # Log the event
        self._logger.info(
            "EVENT %s | source=%s | priority=%s | payload=%s",
            event.name,
            event.source,
            event.priority.name,
            event.payload,
        )
        if self._event_logger is not None:
            self._event_logger.log_event(event)

        # Persist the event
        if self._event_persistence is not None:
            self._event_persistence.persist(event)

        # Enqueue for dispatch
        with self._sequence_lock:
            seq = self._sequence
            self._sequence += 1
        self._queue.put(_PrioritizedEvent(event, seq))

    def emit(self, event: Event) -> None:
        """
        Publish an event (backwards-compatible alias).

        Milestone 1/2 code calls ``bus.emit(Event(...))``.  This
        method delegates to ``publish()`` so existing call sites
        continue to work without modification.
        """
        self.publish(event)

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def subscribe(
        self, event_name: str, listener: EventHandler
    ) -> Subscriber:
        """
        Register a listener for a specific event type name.

        This is the simple Milestone 1 compatible API.

        Args:
            event_name: The event type name to listen for (e.g.
                ``"KernelReady"``).
            listener: A callable that accepts an ``Event`` instance.

        Returns:
            The created ``Subscriber`` object.
        """
        event_filter = EventFilter.for_event_types(event_name)
        return self._subscriber_registry.register(
            handler=listener,
            filter=event_filter,
            source_name="",
        )

    def subscribe_with_filter(
        self,
        handler: EventHandler,
        event_filter: EventFilter,
        source_name: str = "",
    ) -> Subscriber:
        """
        Register a subscriber with a rich event filter.

        Args:
            handler: A callable that accepts an ``Event`` instance.
            event_filter: An ``EventFilter`` describing which events
                this subscriber should receive.
            source_name: Human-readable name of the subscribing
                component (e.g. ``"TaskManager"``).

        Returns:
            The created ``Subscriber`` object.
        """
        return self._subscriber_registry.register(
            handler=handler,
            filter=event_filter,
            source_name=source_name,
        )

    def unsubscribe(self, listener: EventHandler) -> int:
        """
        Remove all subscriptions for a given handler callable.

        Args:
            listener: The handler to unsubscribe.

        Returns:
            The number of subscriptions removed.
        """
        return self._subscriber_registry.unregister_by_handler(listener)

    def unsubscribe_by_id(self, subscriber_id: str) -> bool:
        """
        Remove a specific subscriber by its ID.

        Args:
            subscriber_id: The unique subscriber identifier.

        Returns:
            ``True`` if the subscriber was found and removed.
        """
        return self._subscriber_registry.unregister(subscriber_id)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self) -> int:
        """
        Synchronously process all currently queued events.

        This is useful in tests or when ``auto_start=False``.  It
        processes every event in the queue right now and returns.

        Returns:
            The number of events dispatched.
        """
        count = 0
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, _SentinelEvent):
                break

            self._dispatch_event(item.event)
            self._queue.task_done()
            count += 1
        return count

    def _dispatch_loop(self) -> None:
        """Background thread: pull events off the queue and dispatch."""
        while not self._shutdown_event.is_set() or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if isinstance(item, _SentinelEvent):
                self._queue.task_done()
                break

            try:
                self._dispatch_event(item.event)
            finally:
                self._queue.task_done()

    def _dispatch_event(self, event: Event) -> None:
        """
        Deliver an event to every matching subscriber.

        Exceptions thrown by a subscriber are caught and logged so that
        one broken subscriber never blocks delivery to the rest.
        """
        subscribers = self._subscriber_registry.get_matching_subscribers(event)
        for subscriber in subscribers:
            try:
                subscriber.deliver(event)
            except Exception:
                self._logger.exception(
                    "Subscriber %r (%s) raised an exception while handling event %s.",
                    subscriber.subscriber_id,
                    subscriber.source_name,
                    event.name,
                )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def history(self) -> list[Event]:
        """
        Return a copy of all events emitted since the bus was created.

        Backwards compatible with Milestone 1's ``EventBus.history()``.
        """
        with self._legacy_history_lock:
            return list(self._legacy_history)

    @property
    def subscriber_count(self) -> int:
        """The total number of registered subscribers."""
        return self._subscriber_registry.count()

    def list_subscribers(self) -> list[Subscriber]:
        """Return all registered subscribers."""
        return self._subscriber_registry.list_subscribers()

    @property
    def queue_size(self) -> int:
        """The approximate number of events waiting in the dispatch queue."""
        return self._queue.qsize()

    @property
    def event_history(self) -> EventHistory | None:
        """The attached event history, if any."""
        return self._event_history

    @property
    def subscriber_registry(self) -> SubscriberRegistry:
        """The subscriber registry managed by this bus."""
        return self._subscriber_registry

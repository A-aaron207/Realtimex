"""
Regression tests for Architecture Audit Finding #7:
Asynchronous Event Bus Dispatch Pool.
Verifies that blocking I/O subscribers do not stall the event dispatcher loop or delay other subscribers.
"""

from __future__ import annotations

import logging
import threading
import time

import pytest

from events.bus import EventBus
from events.event import Event


@pytest.fixture
def logger():
    return logging.getLogger("test_async_event_bus")


def test_async_subscriber_does_not_block_subsequent_events(logger):
    """An async subscriber performing slow I/O must not delay delivery of subsequent events."""
    bus = EventBus(logger=logger, auto_start=True)

    slow_executed = threading.Event()
    fast_executed = threading.Event()
    fast_arrival_time = []

    def slow_blocking_handler(event: Event):
        # Simulate blocking I/O (e.g., slow network request or disk write)
        time.sleep(0.3)
        slow_executed.set()

    def fast_handler(event: Event):
        fast_arrival_time.append(time.perf_counter())
        fast_executed.set()

    # Register slow handler as async
    bus.subscribe("SlowEvent", slow_blocking_handler, async_dispatch=True)
    # Register fast handler as standard
    bus.subscribe("FastEvent", fast_handler, async_dispatch=False)

    start_time = time.perf_counter()

    # Publish slow event first, followed immediately by fast event
    bus.publish(Event(name="SlowEvent", source="test"))
    bus.publish(Event(name="FastEvent", source="test"))

    # Fast event MUST arrive quickly (< 0.15s), long before the slow handler finishes (0.3s)
    assert fast_executed.wait(timeout=0.15) is True
    fast_delay = fast_arrival_time[0] - start_time
    assert fast_delay < 0.15, f"Fast handler was blocked by slow handler! Delay: {fast_delay:.3f}s"

    # Slow handler should eventually complete as well
    assert slow_executed.wait(timeout=1.0) is True

    bus.shutdown()


def test_async_subscriber_exception_safety(logger):
    """Exceptions raised in async subscribers are caught and do not halt the bus."""
    bus = EventBus(logger=logger, auto_start=True)

    normal_executed = threading.Event()

    def buggy_async_handler(event: Event):
        raise ValueError("Simulated handler crash")

    def normal_handler(event: Event):
        normal_executed.set()

    bus.subscribe("CrashEvent", buggy_async_handler, async_dispatch=True)
    bus.subscribe("CrashEvent", normal_handler, async_dispatch=False)

    bus.publish(Event(name="CrashEvent", source="test"))

    assert normal_executed.wait(timeout=1.0) is True

    bus.shutdown()


def test_clean_shutdown_with_running_async_workers(logger):
    """EventBus.shutdown cleanly handles active and pending async jobs."""
    bus = EventBus(logger=logger, auto_start=True)

    def sleep_worker(event: Event):
        time.sleep(0.05)

    for i in range(5):
        bus.subscribe(f"Event_{i}", sleep_worker, async_dispatch=True)
        bus.publish(Event(name=f"Event_{i}", source="test"))

    # Immediate shutdown should not raise or hang
    bus.shutdown(timeout=1.0)
    assert bus.is_running is False

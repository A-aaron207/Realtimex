"""
Regression test — Audit Finding: Scheduler Busy-Waiting on Worker Pool Saturation.

Before fix:
    When can_dispatch() returned False, the scheduler popped a step, re-enqueued it,
    then called time.sleep(0.05), looping continuously and burning CPU under saturation.

After fix:
    WorkerManager exposes:
      - wait_for_idle_worker(timeout) — blocks on threading.Event until a worker is freed
      - _worker_available Event — set by execute() after return_worker(); cleared when all busy

    The scheduler calls wait_for_idle_worker() instead of time.sleep(0.05).

Bug: Architecture Audit Finding #2 (Scheduler Busy-Waiting)
"""

import inspect
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from workers.manager import WorkerManager
import scheduler.scheduler as sched_module


# ---------------------------------------------------------------------------
# WorkerManager event mechanism
# ---------------------------------------------------------------------------

class TestWorkerManagerAvailabilityEvent(unittest.TestCase):

    def _make_manager(self) -> WorkerManager:
        event_bus = MagicMock()
        event_bus.publish = MagicMock()
        logger = MagicMock()
        return WorkerManager(
            event_bus=event_bus,
            loaded_modules_provider=lambda: [],
            logger=logger,
        )

    def test_has_worker_available_event(self):
        """WorkerManager must expose _worker_available threading.Event."""
        mgr = self._make_manager()
        self.assertTrue(
            hasattr(mgr, "_worker_available"),
            "WorkerManager must have _worker_available attribute",
        )
        self.assertIsInstance(
            mgr._worker_available,
            threading.Event,
            "_worker_available must be a threading.Event",
        )

    def test_event_initially_set(self):
        """Event must be set initially (workers are available at boot)."""
        mgr = self._make_manager()
        self.assertTrue(
            mgr._worker_available.is_set(),
            "_worker_available must be set initially (workers available)",
        )

    def test_wait_for_idle_worker_method_exists(self):
        """WorkerManager must expose wait_for_idle_worker() as a public method."""
        mgr = self._make_manager()
        self.assertTrue(
            hasattr(mgr, "wait_for_idle_worker") and callable(mgr.wait_for_idle_worker),
            "WorkerManager must expose wait_for_idle_worker() as a public callable",
        )

    def test_wait_returns_true_when_event_set(self):
        """wait_for_idle_worker() must return True immediately when event is set."""
        mgr = self._make_manager()
        mgr._worker_available.set()
        result = mgr.wait_for_idle_worker(timeout=0.1)
        self.assertTrue(result)

    def test_wait_returns_false_on_timeout(self):
        """wait_for_idle_worker() must return False after timeout when event is clear."""
        mgr = self._make_manager()
        mgr._worker_available.clear()
        start = time.monotonic()
        result = mgr.wait_for_idle_worker(timeout=0.1)
        elapsed = time.monotonic() - start
        self.assertFalse(result)
        self.assertGreaterEqual(elapsed, 0.09, "Should have waited close to timeout")

    def test_event_set_after_execute_releases_worker(self):
        """After execute() completes, _worker_available must be set (worker returned to IDLE)."""
        mgr = self._make_manager()

        # Clear the event to simulate all-busy state
        mgr._worker_available.clear()

        # Build a fake context and mock the worker internals
        context = MagicMock()
        context.capability = "plan_task"

        pool = mgr._pools.get("plan_task")
        self.assertIsNotNone(pool, "plan_task pool must exist")

        worker = MagicMock()
        worker.worker_id = "plan_task_worker_01"
        worker.state = MagicMock()
        worker.execute = MagicMock(return_value=MagicMock())

        # Patch pool.acquire_idle_worker to return our mock worker
        # and pool.return_worker to just set the event (mimic real path)
        with patch.object(pool, "acquire_idle_worker", return_value=worker), \
             patch.object(pool, "return_worker"):
            mgr._worker_available.clear()
            # Patch has_idle_worker so we exercise the set() branch
            with patch.object(pool, "has_idle_worker", return_value=False):
                mgr.execute(context)

        self.assertTrue(
            mgr._worker_available.is_set(),
            "_worker_available must be set after execute() returns worker to pool",
        )

    def test_wait_unblocks_when_worker_freed(self):
        """A thread blocked in wait_for_idle_worker must unblock when execute() signals."""
        mgr = self._make_manager()
        mgr._worker_available.clear()

        unblocked = threading.Event()

        def waiter():
            result = mgr.wait_for_idle_worker(timeout=2.0)
            if result:
                unblocked.set()

        t = threading.Thread(target=waiter, daemon=True)
        t.start()

        # Simulate a worker becoming free after 0.1s
        time.sleep(0.05)
        mgr._worker_available.set()

        t.join(timeout=1.0)
        self.assertTrue(unblocked.is_set(), "Waiter thread should have unblocked")


# ---------------------------------------------------------------------------
# Scheduler loop no longer calls time.sleep
# ---------------------------------------------------------------------------

class TestSchedulerNoSleepInLoop(unittest.TestCase):

    def test_scheduling_loop_does_not_call_time_sleep(self):
        """
        _scheduling_loop must NOT contain time.sleep() calls.
        It must use wait_for_idle_worker() instead.
        """
        source = inspect.getsource(sched_module.Scheduler._scheduling_loop)
        self.assertNotIn(
            "time.sleep",
            source,
            "Scheduler._scheduling_loop must not use time.sleep(). "
            "Use worker_manager.wait_for_idle_worker() instead.",
        )

    def test_scheduling_loop_calls_wait_for_idle_worker(self):
        """_scheduling_loop must call wait_for_idle_worker on the worker manager."""
        source = inspect.getsource(sched_module.Scheduler._scheduling_loop)
        self.assertIn(
            "wait_for_idle_worker",
            source,
            "Scheduler._scheduling_loop must call wait_for_idle_worker() when workers are busy.",
        )


if __name__ == "__main__":
    unittest.main()

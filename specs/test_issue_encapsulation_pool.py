"""
Regression test — Audit Finding: Encapsulation violation in DependencyResolver.

Before fix:
    dependency.py accessed pool._workers (private dict) directly,
    bypassing the pool lock and comparing states as raw strings ("IDLE")
    instead of using the WorkerState enum.

After fix:
    WorkerPool.has_idle_worker() is a thread-safe public method.
    DependencyResolver uses it exclusively.

Bug: Architecture Audit Finding #6 (Kernel API Encapsulation)
"""

import threading
import unittest
from unittest.mock import MagicMock

from workers.lifecycle import WorkerState
from workers.pool import WorkerPool


class TestWorkerPoolHasIdleWorker(unittest.TestCase):
    """Tests for the new WorkerPool.has_idle_worker() public method."""

    def _make_pool(self) -> WorkerPool:
        return WorkerPool(capability="test_cap")

    def _make_worker(self, state: WorkerState, worker_id: str = "w1") -> MagicMock:
        w = MagicMock()
        w.worker_id = worker_id
        w.state = state
        w.supported_capability = "test_cap"
        return w

    def test_empty_pool_has_no_idle_worker(self):
        pool = self._make_pool()
        self.assertFalse(pool.has_idle_worker())

    def test_idle_worker_detected(self):
        pool = self._make_pool()
        pool.add_worker(self._make_worker(WorkerState.IDLE, "w1"))
        self.assertTrue(pool.has_idle_worker())

    def test_busy_worker_not_detected_as_idle(self):
        pool = self._make_pool()
        for state in (WorkerState.ASSIGNED, WorkerState.RUNNING, WorkerState.REPORTING,
                      WorkerState.FAILED, WorkerState.TERMINATED):
            pool = self._make_pool()
            pool.add_worker(self._make_worker(state, "w1"))
            self.assertFalse(pool.has_idle_worker(), f"Expected False for state {state}")

    def test_mixed_workers_returns_true_when_any_idle(self):
        pool = self._make_pool()
        pool.add_worker(self._make_worker(WorkerState.RUNNING, "w1"))
        pool.add_worker(self._make_worker(WorkerState.IDLE, "w2"))
        pool.add_worker(self._make_worker(WorkerState.FAILED, "w3"))
        self.assertTrue(pool.has_idle_worker())

    def test_all_busy_returns_false(self):
        pool = self._make_pool()
        pool.add_worker(self._make_worker(WorkerState.RUNNING, "w1"))
        pool.add_worker(self._make_worker(WorkerState.ASSIGNED, "w2"))
        self.assertFalse(pool.has_idle_worker())

    def test_has_idle_worker_is_thread_safe(self):
        """Concurrent calls must not raise or return inconsistent results."""
        pool = self._make_pool()
        pool.add_worker(self._make_worker(WorkerState.IDLE, "w1"))
        results = []
        errors = []

        def probe():
            try:
                results.append(pool.has_idle_worker())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=probe) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")
        self.assertTrue(all(results), "Expected all True, worker was idle throughout")

    def test_no_private_field_access_in_dependency_resolver(self):
        """
        Verify DependencyResolver.can_dispatch does NOT access pool._workers directly.
        It should only call the public has_idle_worker() API.
        """
        import inspect
        import scheduler.dependency as dep_module

        source = inspect.getsource(dep_module.DependencyResolver.can_dispatch)
        self.assertNotIn(
            "_workers",
            source,
            "DependencyResolver.can_dispatch must not access pool._workers directly. "
            "Use pool.has_idle_worker() instead.",
        )

    def test_has_idle_worker_public_api_exists(self):
        """WorkerPool must expose has_idle_worker as a public method."""
        pool = self._make_pool()
        self.assertTrue(
            hasattr(pool, "has_idle_worker") and callable(pool.has_idle_worker),
            "WorkerPool must expose has_idle_worker() as a public callable",
        )


if __name__ == "__main__":
    unittest.main()

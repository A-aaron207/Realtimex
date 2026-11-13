"""
Regression test — Audit Finding: Unsynchronized Subsystems (Thread-Safety).

Before fix:
    DependencyContainer used a plain dict with no lock — concurrent register/resolve
    from multiple boot threads could corrupt the registry.

    LifecycleManager read/wrote _state with no lock — concurrent state-reads and
    transition_to calls could produce duplicate transitions or stale reads.

After fix:
    Both classes use threading.RLock() to guard all public methods.

Bug: Architecture Audit Finding #4 (Unsynchronized Subsystems)
"""

import threading
import unittest

from kernel.container import DependencyContainer
from kernel.lifecycle import KernelState, LifecycleManager, InvalidStateTransition


# ---------------------------------------------------------------------------
# DependencyContainer
# ---------------------------------------------------------------------------

class TestDependencyContainerThreadSafety(unittest.TestCase):

    def test_register_and_resolve_basic(self):
        c = DependencyContainer()
        c.register("svc", 42)
        self.assertEqual(c.resolve("svc"), 42)

    def test_has_returns_false_for_missing(self):
        c = DependencyContainer()
        self.assertFalse(c.has("missing"))

    def test_has_returns_true_after_register(self):
        c = DependencyContainer()
        c.register("x", object())
        self.assertTrue(c.has("x"))

    def test_resolve_raises_key_error_for_missing(self):
        c = DependencyContainer()
        with self.assertRaises(KeyError):
            c.resolve("nonexistent")

    def test_concurrent_register_no_errors(self):
        """Many threads registering distinct keys must not raise or corrupt data."""
        c = DependencyContainer()
        errors = []

        def register_worker(i):
            try:
                c.register(f"key_{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")
        # All 100 keys must be resolvable
        for i in range(100):
            self.assertEqual(c.resolve(f"key_{i}"), i)

    def test_concurrent_resolve_no_errors(self):
        """Many threads resolving the same key concurrently must all get the same value."""
        c = DependencyContainer()
        c.register("shared", "hello")
        results = []
        errors = []

        def read_worker():
            try:
                results.append(c.resolve("shared"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")
        self.assertTrue(all(r == "hello" for r in results))

    def test_has_lock_attribute(self):
        """DependencyContainer must expose an RLock for thread safety."""
        c = DependencyContainer()
        self.assertTrue(
            hasattr(c, "_lock"),
            "DependencyContainer must have a _lock attribute",
        )
        self.assertIsInstance(
            c._lock,
            type(threading.RLock()),
            "DependencyContainer._lock must be a threading.RLock",
        )


# ---------------------------------------------------------------------------
# LifecycleManager
# ---------------------------------------------------------------------------

class TestLifecycleManagerThreadSafety(unittest.TestCase):

    def test_initial_state_is_offline(self):
        lm = LifecycleManager()
        self.assertEqual(lm.state, KernelState.OFFLINE)

    def test_valid_transition_sequence(self):
        lm = LifecycleManager()
        for next_state in (
            KernelState.BOOTING,
            KernelState.INITIALIZING,
            KernelState.READY,
            KernelState.RUNNING,
            KernelState.SHUTTING_DOWN,
            KernelState.OFFLINE,
        ):
            lm.transition_to(next_state)
            self.assertEqual(lm.state, next_state)

    def test_invalid_transition_raises(self):
        lm = LifecycleManager()
        with self.assertRaises(InvalidStateTransition):
            lm.transition_to(KernelState.RUNNING)  # Can't jump from OFFLINE -> RUNNING

    def test_concurrent_state_reads_consistent(self):
        """Many threads reading state while one thread advances it must not crash."""
        lm = LifecycleManager()
        errors = []
        read_values = []

        def reader():
            for _ in range(50):
                try:
                    _ = lm.state  # Must not raise
                    read_values.append(True)
                except Exception as e:
                    errors.append(e)

        # Advance state in a controlled sequence in one writer thread
        def writer():
            try:
                for s in (KernelState.BOOTING, KernelState.INITIALIZING,
                          KernelState.READY, KernelState.RUNNING):
                    lm.transition_to(s)
            except Exception as e:
                errors.append(e)

        readers = [threading.Thread(target=reader) for _ in range(20)]
        writer_thread = threading.Thread(target=writer)

        for t in readers:
            t.start()
        writer_thread.start()
        for t in readers:
            t.join()
        writer_thread.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")

    def test_has_lock_attribute(self):
        """LifecycleManager must expose an RLock for thread safety."""
        lm = LifecycleManager()
        self.assertTrue(
            hasattr(lm, "_lock"),
            "LifecycleManager must have a _lock attribute",
        )
        self.assertIsInstance(
            lm._lock,
            type(threading.RLock()),
            "LifecycleManager._lock must be a threading.RLock",
        )


if __name__ == "__main__":
    unittest.main()

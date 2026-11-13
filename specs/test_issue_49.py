"""
Regression test — Bug #49
==========================
TaskRecovery raises EventBusShutdownError when recover_tasks() is called
after the EventBus has already been shut down.

Root cause:
    tasks/recovery.py called event_bus.publish() unconditionally.
    During test teardown (and on graceful shutdown) the bus is stopped
    before TaskRecovery.recover_tasks() finishes, causing
    EventBusShutdownError to be logged as an ERROR and the recovery
    event to be silently dropped.

Fix:
    Guard the publish() call with ``if self._event_bus.is_running``.
    When the bus is already shut down, emit a WARNING and skip the
    notification — the task is still safely persisted in the repository.

Regression guard:
    These tests must never be deleted.
"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch, call

from events.bus import EventBus
from events.exceptions import EventBusShutdownError
from tasks.recovery import TaskRecovery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id: str = "task-001", state: str = "RUNNING") -> MagicMock:
    """Return a minimal mock Task with the attributes recovery.py reads."""
    task = MagicMock()
    task.task_id = task_id
    task.goal = "test goal"
    task.state = MagicMock()
    task.state.value = state
    task.priority = MagicMock()
    task.priority.value = 10
    return task


def _make_repository(tasks: list) -> MagicMock:
    repo = MagicMock()
    repo.list_active.return_value = tasks
    repo.update.return_value = None
    return repo


def _make_logger() -> logging.Logger:
    return logging.getLogger("test_issue_49")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestBugFix49_RecoveryWithBusShutdown(unittest.TestCase):
    """Bug #49 — EventBusShutdownError during post-shutdown task recovery."""

    # ------------------------------------------------------------------
    # Guard: EventBus.is_running reflects shutdown state
    # ------------------------------------------------------------------

    def test_event_bus_is_running_false_after_shutdown(self):
        """EventBus.is_running must return False once shutdown() is called."""
        bus = EventBus(logger=_make_logger(), auto_start=True)
        self.assertTrue(bus.is_running)
        bus.shutdown()
        self.assertFalse(bus.is_running)

    def test_event_bus_is_running_true_while_active(self):
        """EventBus.is_running must return True while the bus is active."""
        bus = EventBus(logger=_make_logger(), auto_start=True)
        try:
            self.assertTrue(bus.is_running)
        finally:
            bus.shutdown()

    # ------------------------------------------------------------------
    # Core regression: no EventBusShutdownError when bus is shut down
    # ------------------------------------------------------------------

    def test_recover_tasks_does_not_raise_when_bus_is_shut_down(self):
        """
        recover_tasks() MUST NOT raise EventBusShutdownError when the
        EventBus is already shut down — this is the exact bug #49 scenario.
        """
        bus = EventBus(logger=_make_logger(), auto_start=True)
        bus.shutdown()  # shut it down BEFORE recovery runs

        task = _make_task("task-abc", "RUNNING")
        repo = _make_repository([task])

        with patch("tasks.recovery.add_history_entry", return_value=task):
            recovery = TaskRecovery(
                repository=repo,
                event_bus=bus,
                logger=_make_logger(),
            )
            # Must complete without raising EventBusShutdownError
            try:
                count = recovery.recover_tasks()
            except EventBusShutdownError:
                self.fail(
                    "recover_tasks() raised EventBusShutdownError even though "
                    "the fix should guard against publishing to a shut-down bus."
                )

        # The task must still be counted as recovered (repository updated)
        self.assertEqual(count, 1)
        repo.update.assert_called_once()

    def test_recover_tasks_does_not_publish_when_bus_is_shut_down(self):
        """
        When the bus is shut down, publish() must NOT be called at all.
        """
        bus = EventBus(logger=_make_logger(), auto_start=True)
        bus.shutdown()

        task = _make_task("task-xyz", "PENDING")
        repo = _make_repository([task])

        with patch("tasks.recovery.add_history_entry", return_value=task):
            with patch.object(bus, "publish") as mock_publish:
                recovery = TaskRecovery(
                    repository=repo,
                    event_bus=bus,
                    logger=_make_logger(),
                )
                recovery.recover_tasks()
                mock_publish.assert_not_called()

    def test_recover_tasks_emits_warning_when_bus_is_shut_down(self):
        """
        When the bus is shut down, a WARNING must be logged explaining
        why the TaskRecovered event was skipped.
        """
        bus = EventBus(logger=_make_logger(), auto_start=True)
        bus.shutdown()

        task = _make_task("task-warn-check")
        repo = _make_repository([task])

        logger = _make_logger()

        with patch("tasks.recovery.add_history_entry", return_value=task):
            with patch.object(logger, "warning") as mock_warning:
                recovery = TaskRecovery(
                    repository=repo,
                    event_bus=bus,
                    logger=logger,
                )
                recovery.recover_tasks()
                # At least one warning call containing the task id
                warning_msgs = " ".join(
                    str(a) for call_args in mock_warning.call_args_list
                    for a in call_args.args
                )
                self.assertIn("task-warn-check", warning_msgs)

    # ------------------------------------------------------------------
    # Happy path: bus running → event is published normally
    # ------------------------------------------------------------------

    def test_recover_tasks_publishes_event_when_bus_is_running(self):
        """
        When the bus is running, TaskRecovered must be published exactly
        once per recovered task (regression guard for the happy path).
        """
        bus = EventBus(logger=_make_logger(), auto_start=True)

        task = _make_task("task-happy")
        repo = _make_repository([task])

        published_events = []
        bus.subscribe("TaskRecovered", published_events.append)

        try:
            with patch("tasks.recovery.add_history_entry", return_value=task):
                recovery = TaskRecovery(
                    repository=repo,
                    event_bus=bus,
                    logger=_make_logger(),
                )
                count = recovery.recover_tasks()

            # Give the async dispatcher a moment to deliver
            import time
            time.sleep(0.05)
            bus.dispatch()
        finally:
            bus.shutdown()

        self.assertEqual(count, 1)
        self.assertEqual(len(published_events), 1)
        self.assertEqual(published_events[0].name, "TaskRecovered")
        self.assertEqual(published_events[0].payload["task_id"], "task-happy")

    # ------------------------------------------------------------------
    # Multiple tasks: partial publish when bus shuts down mid-loop
    # ------------------------------------------------------------------

    def test_recover_tasks_handles_multiple_tasks_bus_shut_down(self):
        """
        With multiple tasks and a shut-down bus, ALL tasks are still
        persisted in the repository — none are silently dropped.
        """
        bus = EventBus(logger=_make_logger(), auto_start=True)
        bus.shutdown()

        tasks = [_make_task(f"task-{i}") for i in range(5)]
        repo = _make_repository(tasks)

        with patch("tasks.recovery.add_history_entry", side_effect=lambda task, **kw: task):
            recovery = TaskRecovery(
                repository=repo,
                event_bus=bus,
                logger=_make_logger(),
            )
            count = recovery.recover_tasks()

        self.assertEqual(count, 5)
        self.assertEqual(repo.update.call_count, 5)

    def test_recover_tasks_returns_zero_with_no_active_tasks(self):
        """recover_tasks() returns 0 when there are no active tasks."""
        bus = EventBus(logger=_make_logger(), auto_start=False)
        repo = _make_repository([])

        recovery = TaskRecovery(
            repository=repo,
            event_bus=bus,
            logger=_make_logger(),
        )
        count = recovery.recover_tasks()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()

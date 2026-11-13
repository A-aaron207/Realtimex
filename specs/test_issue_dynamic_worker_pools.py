"""
Regression tests for Architecture Audit Finding #1 & #6:
Dynamic worker pools, capability auto-binding on ModuleLoaded, and has_idle_worker encapsulation.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from events.bus import EventBus
from events.event import Event
from loader.loader import LoadedModule
from scheduler.dependency import DependencyResolver
from workflow.step import StepState, WorkflowStep
from workers.api import WorkerAPI
from workers.lifecycle import WorkerState
from workers.manager import WorkerManager


@pytest.fixture
def mock_logger():
    return logging.getLogger("test_dynamic_worker_pools")


@pytest.fixture
def event_bus(mock_logger):
    bus = EventBus(logger=mock_logger, auto_start=False)
    yield bus
    bus.shutdown()


def test_dynamic_register_capability(event_bus, mock_logger):
    """WorkerManager.register_capability explicitly initializes a pool and workers."""
    manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: [],
        logger=mock_logger,
    )

    cap_name = "custom_sentiment_analysis"
    assert cap_name not in manager._pools

    # Register new capability with 2 initial workers
    pool = manager.register_capability(cap_name, initial_workers=2)
    assert pool is not None
    assert pool.capability == cap_name
    assert len(pool._workers) == 2
    assert manager.has_idle_worker(cap_name) is True

    # Registering again returns the existing pool without duplication
    same_pool = manager.register_capability(cap_name, initial_workers=3)
    assert same_pool is pool
    assert len(same_pool._workers) == 2


def test_module_loaded_event_auto_binding(event_bus, mock_logger):
    """Publishing a ModuleLoaded event automatically registers pools for all its capabilities."""
    manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: [],
        logger=mock_logger,
    )

    new_caps = ["audio_transcription", "speech_synthesis"]
    for c in new_caps:
        assert c not in manager._pools

    # Publish ModuleLoaded event
    load_event = Event(
        name="ModuleLoaded",
        source="loader.loader",
        payload={
            "module_id": "audio_suite",
            "name": "Audio Suite",
            "version": "1.0.0",
            "capabilities": new_caps,
        },
    )
    event_bus.publish(load_event)
    # Since bus auto_start=False in this test, dispatch directly via handler
    manager._on_module_loaded(load_event)

    for c in new_caps:
        assert c in manager._pools
        assert manager.has_idle_worker(c) is True
        pool = manager.get_pool(c)
        assert pool is not None
        assert pool.has_idle_worker() is True


def test_get_pool_dynamic_fallback(event_bus, mock_logger):
    """Calling get_pool for an uninitialized capability automatically registers it."""
    manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: [],
        logger=mock_logger,
    )

    novel_cap = "novel_quantum_computation"
    assert novel_cap not in manager._pools

    pool = manager.get_pool(novel_cap)
    assert pool is not None
    assert pool.capability == novel_cap
    assert manager.has_idle_worker(novel_cap) is True


def test_worker_api_forwards_dynamic_capabilities(event_bus, mock_logger):
    """WorkerAPI exposes register_capability and has_idle_worker."""
    manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: [],
        logger=mock_logger,
    )
    api = WorkerAPI(manager)

    cap = "api_registered_capability"
    assert api.has_idle_worker(cap) is False

    pool = api.register_capability(cap, initial_workers=1)
    assert pool is not None
    assert api.has_idle_worker(cap) is True


def test_dependency_resolver_encapsulation(event_bus, mock_logger):
    """DependencyResolver uses worker_manager.has_idle_worker cleanly without inspecting pools."""
    from tasks.states import TaskState

    manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: [],
        logger=mock_logger,
    )

    task_manager = MagicMock()
    mock_task = MagicMock()
    mock_task.state = TaskState.RUNNING
    mock_task.task_id = "task_1"
    task_manager.get_task.return_value = mock_task

    workflow_manager = MagicMock()
    mock_wf = MagicMock()
    mock_wf.parent_task_id = "task_1"
    workflow_manager.load_workflow.return_value = mock_wf

    cap_registry = MagicMock()
    cap_registry.providers.return_value = ["mock_module"]

    resolver = DependencyResolver(
        task_manager=task_manager,
        workflow_manager=workflow_manager,
        capability_registry=cap_registry,
        worker_manager=manager,
        logger=mock_logger,
    )

    step = WorkflowStep(
        step_id="step_1",
        workflow_id="wf_1",
        capability="write_file",
        status=StepState.PENDING,
    )

    # Initial state: write_file has 1 idle worker
    assert resolver.can_dispatch(step) is True

    # Saturated state: acquire worker
    pool = manager.get_pool("write_file")
    worker = pool.acquire_idle_worker()
    assert worker is not None
    assert manager.has_idle_worker("write_file") is False

    # Now resolver should return False
    assert resolver.can_dispatch(step) is False

    # Return worker: resolver should return True
    pool.return_worker(worker.worker_id)
    assert resolver.can_dispatch(step) is True


"""
Tests for FailureClassifier and semantic failure recovery routing.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import pytest

from kernel.api import KernelAPI
from kernel.lifecycle import KernelState
from interfaces.cli.interface import CLIInterface
from tasks.states import TaskState
from kernel.classifier import FailureClassifier, FailureType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


@pytest.fixture(scope="module")
def booted_api():
    # Setup test file logs/test_input.txt
    os.makedirs(LOG_DIRECTORY, exist_ok=True)
    with open(LOG_DIRECTORY / "test_input.txt", "w", encoding="utf-8") as f:
        f.write("Golden workflow verification input file. Realtimex rules.")

    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )
    api.boot()
    yield api
    api.shutdown()


def test_failure_classifier_unit():
    """Unit test for FailureClassifier matching logic."""
    assert FailureClassifier.classify("Rate Limit Exceeded on api request") == FailureType.RESOURCE
    assert FailureClassifier.classify("Missing Permission to write secure directory") == FailureType.PERMISSION
    assert FailureClassifier.classify("Groq model provider is offline") == FailureType.PROVIDER
    assert FailureClassifier.classify("Transient timeout try again") == FailureType.TRANSIENT
    assert FailureClassifier.classify("Simulated logic runtimeerror") == FailureType.LOGIC
    assert FailureClassifier.classify("Totally random generic error message") == FailureType.UNKNOWN


def execute_workflow_to_response(api: KernelAPI, goal: str, timeout: float = 12.0):
    """Helper to run a CLI request and return the task_id, response, and completion flag."""
    api.interface_manager.registry.unregister("cli")

    cli = CLIInterface(
        user_id="test_user",
        interactive=False,
        single_command=goal,
        use_colors=False
    )
    api.interface_manager.register_interface(cli)
    api.interface_manager.start_interface("cli")

    request = api.interface_manager.receive("cli")
    assert request is not None

    response = api.interface_manager.process_request(request)
    task_id = response.metadata.get("task_id")
    assert task_id is not None

    # Wait for status transition
    start_time = time.time()
    while time.time() - start_time < timeout:
        task = api.task_manager.get_task(task_id)
        if task.state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.WAITING_FOR_PERMISSION, TaskState.WAITING_FOR_USER}:
            break
        time.sleep(0.05)

    return task_id, api.task_manager.get_task(task_id)


def test_transient_failure_recovery(booted_api):
    """Verify that a transient failure transitions to RETRYING and successfully completes."""
    task_id, task = execute_workflow_to_response(booted_api, "Test transient failure path", timeout=10.0)
    assert task.state == TaskState.COMPLETED


def test_permission_failure_recovery(booted_api):
    """Verify that a permission failure suspends the task in WAITING_FOR_PERMISSION state."""
    task_id, task = execute_workflow_to_response(booted_api, "Test permission failure path", timeout=10.0)
    assert task.state == TaskState.WAITING_FOR_PERMISSION

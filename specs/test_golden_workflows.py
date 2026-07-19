"""
Integration test suite verifying the 10 Golden Workflows.
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


def execute_workflow(api: KernelAPI, goal: str, timeout: float = 12.0) -> str:
    """Helper to run a CLI request and return the final output."""
    # Unregister existing CLI interface to avoid duplicate registration
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

    # Wait for completion
    start_time = time.time()
    completed = False
    while time.time() - start_time < timeout:
        task = api.task_manager.get_task(task_id)
        if task.state == TaskState.COMPLETED:
            completed = True
            break
        elif task.state == TaskState.FAILED:
            break
        time.sleep(0.05)

    assert completed, f"Workflow execution timed out or failed for goal: {goal}"

    # Verify memory update exists
    memories = api.memory_manager.search(query={"owner": task_id, "scope": "task"})
    assert len(memories) > 0, "No task memory record was created."

    # Return concatenated final response output across all task memories
    return "\n".join(m.content for m in memories)


def test_summarize_text(booted_api):
    output = execute_workflow(booted_api, "Summarize this text: Sprint 1 is complete and verified.")
    assert "Simulated Groq Response" in output or "Sprint 1" in output


def test_answer_question(booted_api):
    output = execute_workflow(booted_api, "Explain recursion with an example")
    assert "recursion" in output.lower() or "Simulated Groq Response" in output


def test_generate_python_code(booted_api):
    output = execute_workflow(booted_api, "Write a Python function to reverse a linked list")
    assert "linked list" in output.lower() or "Simulated Groq Response" in output


def test_explain_concept(booted_api):
    output = execute_workflow(booted_api, "Explain the concept of decorators in Python")
    assert "decorators" in output.lower() or "Simulated Groq Response" in output


def test_research_topic(booted_api):
    output = execute_workflow(booted_api, "Research the history of neural networks")
    # Research produces [search] and [synthesize] steps
    assert "[search]" in output and "[synthesize]" in output


def test_read_local_file(booted_api):
    # Pass path as logs/test_input.txt
    output = execute_workflow(booted_api, "Read local file: logs/test_input.txt")
    assert "Golden workflow verification input" in output


def test_multistep_workflow(booted_api):
    output = execute_workflow(booted_api, "Run a multi-step workflow to read and summarize")
    assert "[read]" in output and "[summarize]" in output and "[write]" in output


def test_parallel_workflow(booted_api):
    output = execute_workflow(booted_api, "Run a parallel workflow to merge search topics")
    assert "[search_a]" in output and "[search_b]" in output and "[merge]" in output


def test_recovery_retry(booted_api):
    # This runs a step that simulates fail on first attempt, then succeeds on retry
    output = execute_workflow(booted_api, "Test recovery retry after a workflow interruption")
    assert "[unstable_step]" in output


def test_permission_request(booted_api):
    output = execute_workflow(booted_api, "Test a permission request check step")
    assert "permissions" in output.lower()

"""
Tests for the Terminal Module.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from kernel.api import KernelAPI
from services.registry import ServiceRegistry
from workers.context import ExecutionContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


@pytest.fixture(scope="module")
def booted_api():
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )
    api.boot()
    yield api
    api.shutdown()


def test_terminal_module_loaded(booted_api):
    """Verify that the terminal module is successfully discovered and loaded."""
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "terminal" in module_loader._loaded_modules
    
    loaded_module = module_loader._loaded_modules["terminal"]
    module_instance = loaded_module.instance
    assert "run_command" in module_instance.capabilities
    assert "spawn_session" in module_instance.capabilities
    assert "execute_session_command" in module_instance.capabilities


def test_run_command(booted_api):
    """Verify the run_command capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["terminal"].instance

    context = ExecutionContext(
        task_id="test_run_task",
        workflow_id="test_run_workflow",
        step_id="step_01",
        capability="run_command",
        input={"command": "echo 'hello world'"},
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("run_command", context)
    assert result["status"] == "SUCCESS"
    assert "hello world" in result["stdout"]
    assert result["exit_code"] == 0


def test_persistent_session(booted_api):
    """Verify persistent shell session transitions (spawn, env exports, directory changes)."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["terminal"].instance

    # 1. Spawn session
    context_spawn = ExecutionContext(
        task_id="test_session_task",
        workflow_id="test_session_workflow",
        step_id="step_01",
        capability="spawn_session",
        input={"cwd": "/"},
        permissions={},
        metadata={}
    )
    res_spawn = module_instance.execute("spawn_session", context_spawn)
    assert res_spawn["status"] == "SUCCESS"
    session_id = res_spawn["session_id"]
    assert res_spawn["cwd"] == "/"

    # 2. Export variable
    context_export = ExecutionContext(
        task_id="test_session_task",
        workflow_id="test_session_workflow",
        step_id="step_02",
        capability="execute_session_command",
        input={"session_id": session_id, "command": "export TEST_VAR=RealtimexVal"},
        permissions={},
        metadata={}
    )
    res_export = module_instance.execute("execute_session_command", context_export)
    assert res_export["status"] == "SUCCESS"

    # 3. Echo variable
    context_echo = ExecutionContext(
        task_id="test_session_task",
        workflow_id="test_session_workflow",
        step_id="step_03",
        capability="execute_session_command",
        input={"session_id": session_id, "command": "echo $TEST_VAR"},
        permissions={},
        metadata={}
    )
    res_echo = module_instance.execute("execute_session_command", context_echo)
    assert res_echo["status"] == "SUCCESS"
    assert "RealtimexVal" in res_echo["stdout"]

    # 4. Change directory
    context_cd = ExecutionContext(
        task_id="test_session_task",
        workflow_id="test_session_workflow",
        step_id="step_04",
        capability="execute_session_command",
        input={"session_id": session_id, "command": f"cd {PROJECT_ROOT}"},
        permissions={},
        metadata={}
    )
    res_cd = module_instance.execute("execute_session_command", context_cd)
    assert res_cd["status"] == "SUCCESS"
    assert res_cd["cwd"] == str(PROJECT_ROOT)

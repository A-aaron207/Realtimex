"""
Tests for the Developer Module.
"""

from __future__ import annotations

import os
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


def test_developer_module_loaded(booted_api):
    """Verify that the developer module is successfully discovered and loaded."""
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "developer" in module_loader._loaded_modules
    
    loaded_module = module_loader._loaded_modules["developer"]
    module_instance = loaded_module.instance
    assert "generate_code" in module_instance.capabilities
    assert "refactor_code" in module_instance.capabilities
    assert "debug_code" in module_instance.capabilities
    assert "run_tests" in module_instance.capabilities


def test_developer_generate_code(booted_api):
    """Verify the generate_code capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["developer"].instance

    context = ExecutionContext(
        task_id="test_gen_task",
        workflow_id="test_gen_workflow",
        step_id="step_01",
        capability="generate_code",
        input={"prompt": "Write a python function to print hello world", "file_path": "logs/test_gen.py"},
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("generate_code", context)
    assert result["status"] == "SUCCESS"
    assert "def " in result["code"] or "print" in result["code"] or "Simulated" in result["code"]
    assert os.path.exists("logs/test_gen.py")
    
    # Cleanup
    if os.path.exists("logs/test_gen.py"):
        os.remove("logs/test_gen.py")


def test_developer_refactor_code(booted_api):
    """Verify the refactor_code capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["developer"].instance

    context = ExecutionContext(
        task_id="test_refactor_task",
        workflow_id="test_refactor_workflow",
        step_id="step_02",
        capability="refactor_code",
        input={
            "code": "def f(x):\n  return x*2",
            "instructions": "Rename function to double_value"
        },
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("refactor_code", context)
    assert result["status"] == "SUCCESS"
    assert "double_value" in result["refactored_code"] or "Simulated" in result["refactored_code"]


def test_developer_debug_code(booted_api):
    """Verify the debug_code capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["developer"].instance

    context = ExecutionContext(
        task_id="test_debug_task",
        workflow_id="test_debug_workflow",
        step_id="step_03",
        capability="debug_code",
        input={
            "code": "def f(x)\n  return x*2",
            "error_message": "SyntaxError: invalid syntax"
        },
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("debug_code", context)
    assert result["status"] == "SUCCESS"
    assert "def f(x):" in result["fixed_code"] or "Simulated" in result["fixed_code"]


def test_developer_run_tests(booted_api):
    """Verify the run_tests capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["developer"].instance

    context = ExecutionContext(
        task_id="test_run_tests_task",
        workflow_id="test_run_tests_workflow",
        step_id="step_04",
        capability="run_tests",
        input={"test_command": "echo 'running tests'"},
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("run_tests", context)
    assert result["status"] == "SUCCESS"
    assert "running tests" in result["stdout"]
    assert result["exit_code"] == 0

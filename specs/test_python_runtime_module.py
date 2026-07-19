"""
Tests for the Python Runtime Module.
"""

from __future__ import annotations

import os
import tempfile
import pytest
from pathlib import Path

from kernel.api import KernelAPI
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


@pytest.fixture(scope="module")
def pyrt(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "python_runtime" in module_loader._loaded_modules
    return module_loader._loaded_modules["python_runtime"].instance


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_pyrt",
        workflow_id="test_pyrt_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def test_python_runtime_loaded(pyrt):
    assert "execute_script" in pyrt.capabilities
    assert "execute_snippet" in pyrt.capabilities
    assert "install_package" in pyrt.capabilities
    assert "list_packages" in pyrt.capabilities


def test_execute_snippet_success(pyrt):
    result = pyrt.execute("execute_snippet", _ctx("execute_snippet", {
        "code": "print('Realtimex Python Runtime')"
    }))
    assert result["status"] == "SUCCESS"
    assert "Realtimex Python Runtime" in result["stdout"]
    assert result["exit_code"] == 0


def test_execute_snippet_syntax_error(pyrt):
    result = pyrt.execute("execute_snippet", _ctx("execute_snippet", {
        "code": "def broken(:\n    pass"
    }))
    assert result["status"] == "FAILED"
    assert result["exit_code"] != 0


def test_execute_script(pyrt, tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("import sys\nprint('arg:', sys.argv[1] if len(sys.argv) > 1 else 'none')\n")

    result = pyrt.execute("execute_script", _ctx("execute_script", {
        "script_path": str(script),
        "args": ["kernel"]
    }))
    assert result["status"] == "SUCCESS"
    assert "arg: kernel" in result["stdout"]


def test_execute_script_missing_file(pyrt):
    result = pyrt.execute("execute_script", _ctx("execute_script", {
        "script_path": "/tmp/does_not_exist_rtx.py"
    }))
    assert result["status"] == "FAILED"
    assert "not found" in result["error"]


def test_list_packages(pyrt):
    result = pyrt.execute("list_packages", _ctx("list_packages", {"format": "columns"}))
    assert result["status"] == "SUCCESS"
    # pip and setuptools should always be present
    assert "pip" in result["stdout"].lower()

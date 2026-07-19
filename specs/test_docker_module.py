"""
Tests for the Docker Module.

Strategy: tests verify module loading and argument-building logic without
requiring a running Docker daemon. subprocess.run is patched so the full
capability dispatch path is exercised safely in any CI environment.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
def docker(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "docker" in module_loader._loaded_modules
    return module_loader._loaded_modules["docker"].instance


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_docker",
        workflow_id="test_docker_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def _mock_proc(stdout: str = "abc123def456", returncode: int = 0) -> MagicMock:
    """Return a mock CompletedProcess-like object."""
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


def test_docker_module_loaded(docker):
    for cap in ["build_image", "run_container", "stop_container", "list_containers", "exec_in_container"]:
        assert cap in docker.capabilities


def test_build_image(docker):
    with patch("subprocess.run", return_value=_mock_proc("")) as mock:
        result = docker.execute("build_image", _ctx("build_image", {
            "tag": "realtimex/test:latest",
            "context_path": ".",
            "build_args": {"ENV": "production"}
        }))
    assert result["status"] == "SUCCESS"
    assert result["image_tag"] == "realtimex/test:latest"
    called_args = mock.call_args[0][0]   # first positional: the list
    assert "build" in called_args
    assert "-t" in called_args
    assert "--build-arg" in called_args


def test_build_image_missing_tag(docker):
    result = docker.execute("build_image", _ctx("build_image", {"context_path": "."}))
    assert result["status"] == "FAILED"
    assert "tag" in result["error"]


def test_run_container(docker):
    with patch("subprocess.run", return_value=_mock_proc("abc123def456")) as mock:
        result = docker.execute("run_container", _ctx("run_container", {
            "image": "nginx:alpine",
            "name": "rtx-nginx",
            "ports": {"8080": "80"},
            "env": {"DEBUG": "true"},
            "detach": True
        }))
    assert result["status"] == "SUCCESS"
    assert result["container_id"] == "abc123def456"[:12]
    called_args = mock.call_args[0][0]
    assert "-p" in called_args
    assert "8080:80" in called_args
    assert "-e" in called_args


def test_run_container_missing_image(docker):
    result = docker.execute("run_container", _ctx("run_container", {}))
    assert result["status"] == "FAILED"
    assert "image" in result["error"]


def test_stop_container(docker):
    with patch("subprocess.run", return_value=_mock_proc()):
        result = docker.execute("stop_container", _ctx("stop_container", {
            "container": "rtx-nginx",
            "remove": False
        }))
    assert result["status"] == "SUCCESS"
    assert result["removed"] is False


def test_stop_and_remove_container(docker):
    with patch("subprocess.run", return_value=_mock_proc()):
        result = docker.execute("stop_container", _ctx("stop_container", {
            "container": "rtx-nginx",
            "remove": True
        }))
    assert result["status"] == "SUCCESS"
    assert result["removed"] is True


def test_list_containers(docker):
    ps_line = "abc123\trtx-nginx\tnginx:alpine\tUp 5 minutes\t0.0.0.0:8080->80/tcp"
    with patch("subprocess.run", return_value=_mock_proc(ps_line)):
        result = docker.execute("list_containers", _ctx("list_containers", {"all": False}))
    assert result["status"] == "SUCCESS"
    assert result["count"] == 1
    assert result["containers"][0]["name"] == "rtx-nginx"
    assert result["containers"][0]["image"] == "nginx:alpine"


def test_exec_in_container(docker):
    with patch("subprocess.run", return_value=_mock_proc("hello")) as mock:
        result = docker.execute("exec_in_container", _ctx("exec_in_container", {
            "container": "rtx-nginx",
            "command": "echo hello"
        }))
    assert result["status"] == "SUCCESS"
    called_args = mock.call_args[0][0]
    assert "exec" in called_args
    assert "rtx-nginx" in called_args

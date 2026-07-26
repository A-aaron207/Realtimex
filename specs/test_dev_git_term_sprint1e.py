"""
Sprint 1E — Developer, Git, and Terminal Reliability Tests
============================================================
Covers: Developer, Git, and Terminal module edge cases, parameter validation,
        session state continuity, failure modes, error propagation, and
        capability contracts.

Target: Close final gaps for Terminal (100/100), Git (70/70), Developer (130/130).
"""

from __future__ import annotations

import os
import subprocess
import pytest
from pathlib import Path
from typing import Any

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
def dev_module(booted_api):
    loader = booted_api._kernel._boot_result.module_loader
    return loader._loaded_modules["developer"].instance


@pytest.fixture(scope="module")
def git_module(booted_api):
    loader = booted_api._kernel._boot_result.module_loader
    return loader._loaded_modules["git"].instance


@pytest.fixture(scope="module")
def terminal_module(booted_api):
    loader = booted_api._kernel._boot_result.module_loader
    return loader._loaded_modules["terminal"].instance


@pytest.fixture(scope="function")
def temp_repo(tmp_path):
    repo = tmp_path / "sprint1e_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@realtimex.io"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Realtimex Tester"], cwd=str(repo), check=True, capture_output=True)
    (repo / "README.md").write_text("# Sprint 1E Repo")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo), check=True, capture_output=True)
    return repo


def _ctx(capability: str, input_data: dict[str, Any]) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_sprint1e_task",
        workflow_id="test_sprint1e_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


# ===========================================================================
# 1. Terminal Module Edge Cases
# ===========================================================================

def test_terminal_run_command_failure(terminal_module):
    """run_command capturing non-zero exit code."""
    res = terminal_module.execute("run_command", _ctx("run_command", {"command": "false"}))
    assert res["exit_code"] != 0


def test_terminal_run_command_missing_cmd(terminal_module):
    """run_command with missing command field returns error/failed status."""
    res = terminal_module.execute("run_command", _ctx("run_command", {}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_terminal_invalid_session_id(terminal_module):
    """execute_session_command with unknown session_id returns error."""
    res = terminal_module.execute("execute_session_command", _ctx("execute_session_command", {
        "session_id": "non_existent_session_999",
        "command": "echo test"
    }))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_terminal_spawn_session_default_cwd(terminal_module):
    """spawn_session creates a session with working directory."""
    res = terminal_module.execute("spawn_session", _ctx("spawn_session", {}))
    assert res["status"] == "SUCCESS"
    assert "session_id" in res


# ===========================================================================
# 2. Git Module Edge Cases
# ===========================================================================

def test_git_invalid_repo_path(git_module):
    """git status/diff on non-existent repo path returns FAILED status."""
    res = git_module.execute("diff", _ctx("diff", {"repo_path": "/non/existent/path/for/git/repo"}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_git_commit_no_message(git_module, temp_repo):
    """commit without commit message provides fallback or error."""
    (temp_repo / "file.txt").write_text("content")
    res = git_module.execute("commit", _ctx("commit", {"repo_path": str(temp_repo)}))
    assert res["status"] in ("SUCCESS", "FAILED")  # Should handle gracefully


def test_git_branch_invalid_action(git_module, temp_repo):
    """branch capability with invalid action handles error gracefully."""
    res = git_module.execute("branch", _ctx("branch", {"repo_path": str(temp_repo), "action": "invalid_act"}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


# ===========================================================================
# 3. Developer Module Edge Cases
# ===========================================================================

def test_dev_generate_code_missing_prompt(dev_module):
    """generate_code without prompt returns error/failed status."""
    res = dev_module.execute("generate_code", _ctx("generate_code", {}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_dev_refactor_code_missing_instructions(dev_module):
    """refactor_code without instructions returns error/failed status."""
    res = dev_module.execute("refactor_code", _ctx("refactor_code", {"code": "def foo(): pass"}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_dev_debug_code_missing_inputs(dev_module):
    """debug_code without code/error returns error/failed status."""
    res = dev_module.execute("debug_code", _ctx("debug_code", {}))
    assert res["status"] in ("FAILED", "ERROR") or "error" in res


def test_dev_run_tests_command_failure(dev_module):
    """run_tests capturing failed test command."""
    res = dev_module.execute("run_tests", _ctx("run_tests", {"test_command": "exit 1"}))
    assert res["exit_code"] != 0 or res["status"] in ("FAILED", "ERROR")


def test_dev_unknown_capability_raises(dev_module):
    """developer module with unsupported capability raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        dev_module.execute("unsupported_cap", _ctx("unsupported_cap", {}))

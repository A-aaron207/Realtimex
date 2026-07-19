"""
Tests for the Git Module.
"""

from __future__ import annotations

import os
import tempfile
import subprocess
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
def git_module(booted_api):
    """Resolve and return the Git Module instance."""
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "git" in module_loader._loaded_modules
    return module_loader._loaded_modules["git"].instance


@pytest.fixture(scope="function")
def temp_repo(tmp_path):
    """Create a temporary, initialized git repo for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), check=True, capture_output=True)
    # Initial commit so HEAD exists
    (repo / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo), check=True, capture_output=True)
    return repo


def test_git_module_loaded(git_module):
    """Verify the Git Module is discovered and loaded with all capabilities."""
    assert "clone_repo" in git_module.capabilities
    assert "commit" in git_module.capabilities
    assert "branch" in git_module.capabilities
    assert "diff" in git_module.capabilities


def test_commit(git_module, temp_repo):
    """Verify committing staged changes works correctly."""
    (temp_repo / "hello.txt").write_text("Hello Realtimex")

    context = ExecutionContext(
        task_id="test_git_commit",
        workflow_id="test_git_workflow",
        step_id="step_01",
        capability="commit",
        input={"repo_path": str(temp_repo), "message": "feat: add hello.txt"},
        permissions={},
        metadata={}
    )

    result = git_module.execute("commit", context)
    assert result["status"] == "SUCCESS"
    assert "hello.txt" in result["stdout"] or "feat" in result["stdout"]


def test_branch_list(git_module, temp_repo):
    """Verify listing branches returns the current branch."""
    context = ExecutionContext(
        task_id="test_git_branch_list",
        workflow_id="test_git_workflow",
        step_id="step_02",
        capability="branch",
        input={"repo_path": str(temp_repo), "action": "list"},
        permissions={},
        metadata={}
    )

    result = git_module.execute("branch", context)
    assert result["status"] == "SUCCESS"
    # At least the initial branch (main or master) should be listed
    assert result["stdout"]


def test_branch_create_and_switch(git_module, temp_repo):
    """Verify creating and switching branches."""
    ctx_create = ExecutionContext(
        task_id="test_git_branch_create",
        workflow_id="test_git_workflow",
        step_id="step_03",
        capability="branch",
        input={"repo_path": str(temp_repo), "action": "create", "name": "feature/test-branch"},
        permissions={},
        metadata={}
    )
    result_create = git_module.execute("branch", ctx_create)
    assert result_create["status"] == "SUCCESS"

    ctx_switch = ExecutionContext(
        task_id="test_git_branch_switch",
        workflow_id="test_git_workflow",
        step_id="step_04",
        capability="branch",
        input={"repo_path": str(temp_repo), "action": "switch", "name": "feature/test-branch"},
        permissions={},
        metadata={}
    )
    result_switch = git_module.execute("branch", ctx_switch)
    assert result_switch["status"] == "SUCCESS"


def test_diff(git_module, temp_repo):
    """Verify that diff returns output after modifying a file."""
    (temp_repo / "README.md").write_text("# Test Repo\n\nModified content.")

    context = ExecutionContext(
        task_id="test_git_diff",
        workflow_id="test_git_workflow",
        step_id="step_05",
        capability="diff",
        input={"repo_path": str(temp_repo)},
        permissions={},
        metadata={}
    )

    result = git_module.execute("diff", context)
    assert result["status"] == "SUCCESS"
    assert "Modified content" in result["diff_output"] or "README" in result["diff_output"]

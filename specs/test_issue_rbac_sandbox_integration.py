"""
Regression tests for Architecture Audit Finding #5:
Integration between Interface Authentication Roles and Worker Sandbox Permissions.
Ensures RBAC security limits are propagated into ExecutionContext and enforced at runtime.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from permissions.decision import PermissionDecision
from permissions.manager import PermissionManager
from permissions.persistence import PermissionPersistence
from workers.context import ExecutionContext
from workers.exceptions import WorkerExecutionError
from workers.runtime import WorkerRuntime


@pytest.fixture
def permission_manager(tmp_path):
    persistence = PermissionPersistence(directory=tmp_path)
    return PermissionManager(
        persistence=persistence,
        logger=logging.getLogger("test_rbac_sandbox"),
    )


def test_rbac_role_evaluation_rules(permission_manager):
    """Verify is_role_allowed checks capabilities and actions against role limits."""
    # Admin can do everything
    assert permission_manager.is_role_allowed("admin", "write", "write_file") is True
    assert permission_manager.is_role_allowed("admin", "execute", "run_command") is True

    # User can perform standard actions
    assert permission_manager.is_role_allowed("user", "read", "read_file") is True
    assert permission_manager.is_role_allowed("user", "write", "write_file") is True
    # User cannot perform system admin actions
    assert permission_manager.is_role_allowed("user", "system_admin", "terminal") is False

    # Viewer can only perform read actions
    assert permission_manager.is_role_allowed("viewer", "read", "read_file") is True
    assert permission_manager.is_role_allowed("viewer", "search", "web_search") is True
    assert permission_manager.is_role_allowed("viewer", "write", "write_file") is False
    assert permission_manager.is_role_allowed("viewer", "execute", "run_command") is False
    assert permission_manager.is_role_allowed("viewer", "delete", "delete_file") is False


def test_permission_request_enforces_user_role(permission_manager):
    """PermissionManager.request denies privileged actions when user_role is restricted."""
    # Viewer attempting write action
    decision = permission_manager.request(
        task_id="t1",
        worker_id="w1",
        action="write",
        target="/tmp/test.txt",
        requested_capability="write_file",
        risk_level="high",
        metadata={"user_role": "viewer"},
    )
    assert decision.approved is False
    assert "RBAC violation" in decision.reason
    assert "viewer" in decision.reason

    # Admin attempting same action is evaluated normally (not blocked by RBAC)
    admin_decision = permission_manager.request(
        task_id="t2",
        worker_id="w2",
        action="write",
        target="/tmp/test.txt",
        requested_capability="write_file",
        risk_level="low",
        metadata={"user_role": "admin"},
    )
    assert admin_decision.approved is True


def test_execution_context_security_propagation():
    """ExecutionContext serializes and deserializes user_role, user_id, and auth_context."""
    ctx = ExecutionContext(
        task_id="task_123",
        workflow_id="wf_456",
        step_id="step_789",
        capability="write_file",
        user_role="viewer",
        user_id="user_john_doe",
        auth_context={"ip": "127.0.0.1", "auth_method": "token"},
    )

    data = ctx.to_dict()
    assert data["user_role"] == "viewer"
    assert data["user_id"] == "user_john_doe"
    assert data["auth_context"]["auth_method"] == "token"

    restored = ExecutionContext.from_dict(data)
    assert restored.user_role == "viewer"
    assert restored.user_id == "user_john_doe"
    assert restored.auth_context == ctx.auth_context


def test_worker_runtime_enforces_viewer_role(permission_manager, monkeypatch):
    """WorkerRuntime blocks execution when ExecutionContext has a viewer role attempting a write capability."""
    from services.base import SimpleService
    from services.registry import ServiceRegistry

    registry = ServiceRegistry(set_as_current=True)
    registry.register(SimpleService("permission_manager", {"manager": permission_manager}))

    mock_event_bus = MagicMock()
    mock_module = MagicMock()
    mock_module.manifest.permissions = {}
    mock_module.instance.write_file = MagicMock(return_value={"status": "written"})

    worker = WorkerRuntime(
        worker_id="write_worker_01",
        worker_type="agent_worker",
        supported_capability="write_file",
        event_bus=mock_event_bus,
        module_resolver=lambda mod_id: mock_module,
    )
    from workers.lifecycle import WorkerState
    worker.set_state(WorkerState.STARTING)
    worker.set_state(WorkerState.IDLE)

    ctx = ExecutionContext(
        task_id="task_audit",
        workflow_id="wf_audit",
        step_id="step_audit",
        capability="write_file",
        input={"path": "/tmp/sample.txt", "content": "hello"},
        configuration={"provider_id": "filesystem"},
        user_role="viewer",
        user_id="viewer_user",
    )

    report = worker.execute(ctx)
    assert report.status.value == "FAILED"
    assert "Action denied: RBAC violation" in report.error_message


def test_custom_role_limits_configuration(permission_manager):
    """Roles can be customized with configure_role_limits."""
    permission_manager.configure_role_limits(
        role="data_analyst",
        allowed_capabilities=["select_records", "query_database", "summarize_text"],
        disallowed_actions=["drop", "delete", "truncate"],
    )

    assert permission_manager.is_role_allowed("data_analyst", "query", "select_records") is True
    assert permission_manager.is_role_allowed("data_analyst", "query", "write_file") is False
    assert permission_manager.is_role_allowed("data_analyst", "drop", "select_records") is False

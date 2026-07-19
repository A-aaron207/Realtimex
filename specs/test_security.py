"""
Unit tests for the Realtimex Security & Sandboxing System.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import pytest
from unittest.mock import MagicMock

from events.bus import EventBus
from security import (
    SecurityManager,
    SecurityContext,
    SandboxLevel,
    FilesystemPolicy,
    NetworkPolicy,
    ProcessPolicy,
    Capabilities,
    SecurityError,
    SandboxViolationError,
    ResourceLimitExceededError,
)


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def event_bus():
    """Fixture for Event Bus."""
    return MagicMock(spec=EventBus)


def test_security_context_and_capabilities(event_bus):
    """Test security context mapping and capabilities validation."""
    mgr = SecurityManager(event_bus=event_bus)
    
    # LEVEL_0: Kernel context (always allowed)
    kernel_ctx = mgr.create_context(
        task_id="t-0", module_id="m-kernel", worker_id="w-kernel",
        sandbox_level=SandboxLevel.LEVEL_0
    )
    assert mgr.verify(kernel_ctx, Capabilities.PROCESS_SPAWN)
    
    # LEVEL_2: Standard context (requires explicit capability token)
    std_ctx = mgr.create_context(
        task_id="t-1", module_id="m-std", worker_id="w-std",
        allowed_capabilities=[Capabilities.FILESYSTEM_READ],
        sandbox_level=SandboxLevel.LEVEL_2
    )
    assert mgr.verify(std_ctx, Capabilities.FILESYSTEM_READ)
    assert not mgr.verify(std_ctx, Capabilities.NETWORK_CONNECT)
    
    # EventBus trigger check
    assert event_bus.publish.called
    event = event_bus.publish.call_args[0][0]
    assert event.name == "PermissionVerified"
    assert event.payload["decision"] == "DENIED"


def test_filesystem_isolation_policy(temp_dir):
    """Test filesystem isolation workspace confinement and traversal attacks."""
    from security.filesystem import FilesystemIsolator
    
    workspace = os.path.join(temp_dir, "workspace")
    os.makedirs(workspace, exist_ok=True)
    
    isolator = FilesystemIsolator(
        policy=FilesystemPolicy.WORKSPACE_ONLY,
        workspace_dir=workspace
    )
    
    # Allow path inside workspace
    inside_path = os.path.join(workspace, "subfolder", "data.json")
    assert isolator.is_path_allowed(inside_path, write=True)
    
    # Reject path traversal escape attempt
    traversal_path = os.path.join(workspace, "..", "etc", "passwd")
    assert not isolator.is_path_allowed(traversal_path)
    
    # Read-only policy
    ro_isolator = FilesystemIsolator(
        policy=FilesystemPolicy.READ_ONLY,
        workspace_dir=workspace
    )
    assert ro_isolator.is_path_allowed(inside_path, write=False)
    assert not ro_isolator.is_path_allowed(inside_path, write=True)

    # Approved directories policy
    app_dir = os.path.join(temp_dir, "approved")
    os.makedirs(app_dir, exist_ok=True)
    app_isolator = FilesystemIsolator(
        policy=FilesystemPolicy.APPROVED_DIRECTORIES,
        approved_dirs=[app_dir]
    )
    assert app_isolator.is_path_allowed(os.path.join(app_dir, "log.txt"))
    assert not app_isolator.is_path_allowed(inside_path)


def test_network_isolation_policy():
    """Test network outbound isolation policies and domain whitelists."""
    from security.network import NetworkIsolator
    
    # Localhost only
    local_isolator = NetworkIsolator(policy=NetworkPolicy.LOCALHOST_ONLY)
    assert local_isolator.is_connection_allowed("http://localhost:8000")
    assert local_isolator.is_connection_allowed("127.0.0.1")
    assert not local_isolator.is_connection_allowed("https://google.com")
    
    # Approved domains
    domain_isolator = NetworkIsolator(
        policy=NetworkPolicy.APPROVED_DOMAINS,
        approved_domains=["github.com", "openai.com"]
    )
    assert domain_isolator.is_connection_allowed("https://github.com/realtimex")
    assert domain_isolator.is_connection_allowed("api.openai.com")
    assert not domain_isolator.is_connection_allowed("http://malicious.ru")


def test_process_isolation_policy():
    """Test process spawning restrictions and command whitelists."""
    from security.processes import ProcessIsolator
    
    # No spawn
    ns_isolator = ProcessIsolator(policy=ProcessPolicy.NO_SPAWN)
    assert not ns_isolator.is_process_spawn_allowed("python main.py")
    
    # Approved only
    app_isolator = ProcessIsolator(
        policy=ProcessPolicy.APPROVED_ONLY,
        approved_commands=["git", "/usr/bin/curl"]
    )
    assert app_isolator.is_process_spawn_allowed("git commit -m 'test'")
    assert app_isolator.is_process_spawn_allowed("/usr/bin/curl -s https://google.com")
    assert not app_isolator.is_process_spawn_allowed("rm -rf /")


def test_resource_monitoring_limits():
    """Test ResourceMonitor tracking and limit enforcement checks."""
    from security.resources import ResourceMonitor
    
    monitor = ResourceMonitor()
    ctx = SecurityContext(
        task_id="t-res", module_id="m-res", worker_id="w-res",
        resource_limits={
            "max_cpu_percent": 80.0,
            "max_memory_mb": 1024.0,
            "max_duration_sec": 1.0
        }
    )
    
    monitor.register_task("t-res")
    
    # Normal usage passes
    monitor.check_task_limits("t-res", current_memory_mb=500.0, current_cpu_percent=40.0, context=ctx)
    
    # Memory exceed raises
    with pytest.raises(ResourceLimitExceededError):
        monitor.check_task_limits("t-res", current_memory_mb=1200.0, current_cpu_percent=40.0, context=ctx)
        
    # CPU exceed raises
    with pytest.raises(ResourceLimitExceededError):
        monitor.check_task_limits("t-res", current_memory_mb=500.0, current_cpu_percent=90.0, context=ctx)
        
    # Duration exceed raises after small sleep
    time.sleep(1.1)
    with pytest.raises(ResourceLimitExceededError):
        monitor.check_task_limits("t-res", current_memory_mb=500.0, current_cpu_percent=40.0, context=ctx)
        
    monitor.deregister_task("t-res")


def test_sandbox_lifecycle_and_enforcement(temp_dir, event_bus):
    """Test Sandbox manager registration and safety enforcer violations."""
    mgr = SecurityManager(event_bus=event_bus)
    ctx = mgr.create_context(
        task_id="t-sb", module_id="m-sb", worker_id="w-sb",
        sandbox_level=SandboxLevel.LEVEL_3
    )
    
    workspace = os.path.join(temp_dir, "sb_workspace")
    os.makedirs(workspace, exist_ok=True)
    
    # Create Sandbox
    sandbox = mgr.create_sandbox(
        context=ctx,
        workspace_dir=workspace,
        approved_domains=["github.com"]
    )
    assert sandbox.sandbox_id is not None
    assert event_bus.publish.called
    
    # Filesystem check inside workspace is allowed
    mgr.enforce(sandbox.sandbox_id, "filesystem_read", os.path.join(workspace, "manifest.json"))
    
    # Filesystem escape is blocked
    escape_path = os.path.join(temp_dir, "host_secret.txt")
    with pytest.raises(SandboxViolationError):
        mgr.enforce(sandbox.sandbox_id, "filesystem_read", escape_path)
        
    # Network check inside whitelist is allowed (Wait, Level 3 has NO_NETWORK, so even github should be blocked!)
    # Let's verify that Level 3 blocks everything network-related!
    with pytest.raises(SandboxViolationError):
        mgr.enforce(sandbox.sandbox_id, "network_connect", "https://github.com")
        
    # Destroy Sandbox
    mgr.destroy_sandbox(sandbox.sandbox_id)
    assert mgr.status(sandbox.sandbox_id)["active_sandboxes"] == 0

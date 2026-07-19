"""
Kernel Integration & Alpha Verification Tests for Realtimex (Milestone 20).

Verifies successful booting of the Kernel, presence of all 19 subsystems,
and participates in a full end-to-end task execution pipeline.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from kernel.api import KernelAPI
from kernel.lifecycle import KernelState
from tasks.states import TaskState
from tasks.task import TaskPriority
from events.event import Event


@pytest.fixture
def temp_env():
    """Sets up a clean temporary workspace for kernel boot configuration and logs."""
    temp_dir = tempfile.mkdtemp()
    
    # Paths
    config_dir = Path(temp_dir) / "config"
    log_dir = Path(temp_dir) / "logs"
    modules_dir = Path(temp_dir) / "modules"
    
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(modules_dir, exist_ok=True)
    
    # Create configuration
    config_data = {
        "kernel": {
            "name": "realtimex-integration-kernel",
            "version": "0.9.0-alpha",
            "environment": "integration-testing"
        },
        "logging": {
            "level": "DEBUG",
            "filename": "kernel.log"
        },
        "event_bus": {
            "enabled": True,
            "history_max_size": 1000,
            "persistence_filename": "events.jsonl",
            "event_log_filename": "event_log.jsonl"
        },
        "task_system": {
            "enabled": True,
            "tasks_directory": "tasks"
        },
        "workflow_engine": {
            "enabled": True,
            "workflows_directory": "workflows"
        },
        "service_registry": {
            "enabled": True
        },
        "capability_registry": {
            "enabled": True
        },
        "recovery_manager": {
            "enabled": True
        }
    }
    
    config_path = config_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    yield config_path, log_dir, modules_dir
    
    shutil.rmtree(temp_dir)


def test_kernel_boot_and_subsystem_presence(temp_env):
    """Test that all 19 subsystems boot successfully and are correctly registered."""
    config_path, log_dir, modules_dir = temp_env
    
    # Initialize and boot kernel
    api = KernelAPI(config_path=config_path, log_directory=log_dir, modules_root=modules_dir)
    api.boot()
    
    try:
        # 1. State Verification
        assert api._kernel.state == KernelState.RUNNING
        
        # 2. Subsystem Presence Verifications
        # Core
        assert api._kernel is not None
        assert api.event_manager is not None
        assert api.task_manager is not None
        assert api.task_api is not None
        assert api.workflow_manager is not None
        assert api.workflow_api is not None
        assert api.worker_manager is not None
        assert api.worker_api is not None
        assert api.scheduler is not None
        assert api.scheduler_api is not None
        assert api.capability_registry is not None
        
        # Newer integrated subsystems
        assert api.config_manager is not None
        assert api.observability is not None
        assert api.policy_manager is not None
        assert api.security_manager is not None
        assert api.interface_manager is not None
        assert api.memory_manager is not None
        assert api.model_gateway is not None
        assert api.cognitive_engine is not None
        assert api.permission_manager is not None
        
        # 3. Quick properties verification
        # 3. Quick properties verification
        status = api.status()
        assert status["state"] in ("RUNNING", "KernelState.RUNNING")
        assert status["kernel_name"] == "realtimex-integration-kernel"
        assert status["version"] == "0.9.0-alpha"
        
    finally:
        api.shutdown()


def test_end_to_end_task_execution_participation(temp_env):
    """
    Test a complete task execution lifecycle verifying participation of:
    - Events
    - Memory
    - Permissions
    - Policies
    - Logging / Observability
    """
    config_path, log_dir, modules_dir = temp_env
    
    api = KernelAPI(config_path=config_path, log_directory=log_dir, modules_root=modules_dir)
    api.boot()
    
    try:
        # Collect emitted events for participation validation
        emitted_names = []
        def event_watcher(event: Event):
            emitted_names.append(event.name)
            
        from events.filters import EventFilter
        api.event_manager.subscribe_with_filter(
            handler=event_watcher,
            event_filter=EventFilter(wildcard_patterns=("*",)),
            source_name="IntegrationWatcher"
        )
        
        # 1. Register permission security manifest
        from permissions.registry import SecurityManifest
        manifest = SecurityManifest(
            entity_id="test_agent",
            allowed_actions=["task_plan", "data_read"],
            allowed_targets=["*"]
        )
        api.permission_manager.registry.register_manifest(manifest)
        
        # 2. Register operational policies
        policy = {
            "policy_id": "task_limits",
            "name": "Limit Normal tasks",
            "version": "1.0.0",
            "category": "permissions",
            "conditions": [{"field": "priority", "operator": "eq", "value": "NORMAL"}],
            "effect": "allow",
            "priority": 10,
            "enabled": True
        }
        api.policy_manager.register(policy)
        
        # 3. Create Memory Record
        memory_rec = api.memory_manager.create(
            scope="global",
            owner="integration",
            content="Alpha testing context",
            source="user",
            tags=["alpha", "test"]
        )
        assert memory_rec is not None
        assert api.memory_manager.retrieve(memory_rec.memory_id).content == "Alpha testing context"
        
        # 4. Request / Evaluate permissions & policies
        perm_req = api.permission_manager.request(
            task_id="task_001",
            worker_id="test_agent",
            action="task_plan",
            target="*",
            requested_capability="task_plan"
        )
        assert perm_req.approved
        
        policy_decision = api.policy_manager.evaluate("permissions", {"priority": "NORMAL"})
        assert policy_decision == "allow"
        
        # 5. Create and run task through lifecycle
        task = api.task_manager.create_task(
            goal="Execute Milestone 20 Integration Task",
            priority=TaskPriority.NORMAL
        )
        assert task.state == TaskState.CREATED
        
        # Progress state
        api.task_manager.update_state(task.task_id, TaskState.PLANNING)
        api.task_manager.update_state(task.task_id, TaskState.QUEUED)
        api.task_manager.update_state(task.task_id, TaskState.RUNNING)
        api.task_manager.update_progress(task.task_id, 50)
        api.task_manager.update_state(task.task_id, TaskState.COMPLETED)
        
        # Wait for async updates to populate
        time.sleep(0.3)
        
        # 6. Verify Logging / Observability
        log_file = log_dir / "realtimex.log"
        assert log_file.exists()
        
        # 7. Verify Events participation
        assert "MemoryCreated" in emitted_names
        assert "PermissionApproved" in emitted_names
        assert "TaskCreated" in emitted_names
        assert "TaskUpdated" in emitted_names
        assert "ProgressUpdated" in emitted_names
        
    finally:
        api.shutdown()

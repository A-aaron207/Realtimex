"""
Unit tests for the Realtimex Policy Engine.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock

from events.bus import EventBus
from policy import (
    PolicyManager,
    PolicyValidationError,
    PolicyConflictError,
    PolicyVersionError,
    PolicyError,
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


def test_policy_schema_validation(event_bus):
    """Test policy schema structure and field validator constraints."""
    mgr = PolicyManager(event_bus=event_bus)
    
    # Valid policy
    valid_policy = {
        "policy_id": "pol-sec-01",
        "name": "Security Check",
        "version": "1.0.0",
        "category": "security",
        "conditions": [{"field": "user.role", "operator": "equals", "value": "admin"}],
        "effect": "allow",
        "priority": 10,
        "enabled": True,
        "metadata": {}
    }
    success, errors = mgr.validate(valid_policy)
    assert success
    assert len(errors) == 0

    # Invalid policy: missing required fields
    invalid_policy = {
        "policy_id": "pol-sec-01",
        "name": "Security Check"
    }
    success, errors = mgr.validate(invalid_policy)
    assert not success
    assert "Missing required field" in errors[0]

    # Invalid policy: category value check
    invalid_cat = valid_policy.copy()
    invalid_cat["category"] = "unsupported_cat"
    success, errors = mgr.validate(invalid_cat)
    assert not success
    assert "category" in errors[0]

    # Invalid policy: condition dict key check
    invalid_cond = valid_policy.copy()
    invalid_cond["conditions"] = [{"field": "user.role", "operator": "equals"}]
    success, errors = mgr.validate(invalid_cond)
    assert not success
    assert "missing required key: 'value'" in errors[0]


def test_rule_compiler_operators():
    """Test condition compilers and dot-notated dictionary path lookups."""
    from policy.compiler import RuleCompiler
    compiler = RuleCompiler()
    
    context = {
        "user": {
            "role": "admin",
            "age": 30,
            "tags": ["ai", "dev"]
        },
        "ip": "192.168.1.50"
    }
    
    # Test Equals (eq)
    cond_eq = compiler.compile_condition({"field": "user.role", "operator": "equals", "value": "admin"})
    assert cond_eq(context)
    
    # Test Greater Than (gt)
    cond_gt = compiler.compile_condition({"field": "user.age", "operator": "gt", "value": 25})
    assert cond_gt(context)
    
    # Test Contains
    cond_cont = compiler.compile_condition({"field": "user.tags", "operator": "contains", "value": "ai"})
    assert cond_cont(context)
    
    # Test Regex
    cond_regex = compiler.compile_condition({"field": "ip", "operator": "regex", "value": r"^192\.168\."})
    assert cond_regex(context)


def test_evaluator_conflict_resolution(event_bus):
    """Test conflict resolution strategies priority, first match, and deny overrides."""
    # Register priority allow policy (priority=10)
    p_allow = {
        "policy_id": "pol-allow",
        "name": "Allow Rule",
        "version": "1.0.0",
        "category": "security",
        "conditions": [{"field": "user.role", "operator": "eq", "value": "user"}],
        "effect": "allow",
        "priority": 10,
        "enabled": True
    }
    # Register priority deny policy (priority=20)
    p_deny = {
        "policy_id": "pol-deny",
        "name": "Deny Rule",
        "version": "1.0.0",
        "category": "security",
        "conditions": [{"field": "user.role", "operator": "eq", "value": "user"}],
        "effect": "deny",
        "priority": 20,
        "enabled": True
    }
    
    context = {"user": {"role": "user"}}
    
    # Priority resolution strategy (highest wins: deny=20 > allow=10)
    mgr_priority = PolicyManager(event_bus=event_bus, resolution_strategy="priority")
    mgr_priority.register(p_allow)
    mgr_priority.register(p_deny)
    assert mgr_priority.evaluate("security", context) == "deny"
    
    # Deny Override strategy (any matched deny wins)
    mgr_deny_override = PolicyManager(event_bus=event_bus, resolution_strategy="deny_override")
    p_allow_high = p_allow.copy()
    p_allow_high["priority"] = 100  # allow priority is much higher
    mgr_deny_override.register(p_allow_high)
    mgr_deny_override.register(p_deny)
    assert mgr_deny_override.evaluate("security", context) == "deny"

    # First Match strategy
    mgr_first = PolicyManager(event_bus=event_bus, resolution_strategy="first_match")
    mgr_first.register(p_allow)
    mgr_first.register(p_deny)
    # Registry returns in order of insertion, so pol-allow wins
    assert mgr_first.evaluate("security", context) == "allow"


def test_policy_loader_directory(temp_dir):
    """Test PolicyLoader reads files from folder directory."""
    # Write JSON policy
    p_json = {
        "policy_id": "pol-json",
        "name": "JSON Policy",
        "version": "1.0.0",
        "category": "memory",
        "conditions": [],
        "effect": "allow",
        "priority": 1,
        "enabled": True
    }
    with open(os.path.join(temp_dir, "policy.json"), "w") as f:
        json.dump(p_json, f)
        
    # Write simple YAML policy
    yaml_lines = """
policy_id: "pol-yaml"
name: "YAML Policy"
version: "1.0.0"
category: "scheduler"
conditions: []
effect: "deny"
priority: 5
enabled: true
"""
    with open(os.path.join(temp_dir, "policy.yaml"), "w") as f:
        f.write(yaml_lines)
        
    mgr = PolicyManager(policy_dir=temp_dir)
    assert len(mgr.list_policies()) == 2
    
    # Verify loaded attributes
    p_yaml_loaded = mgr.registry.get("pol-yaml")
    assert p_yaml_loaded is not None
    assert p_yaml_loaded["category"] == "scheduler"
    assert p_yaml_loaded["effect"] == "deny"


def test_policy_version_history_and_rollback(event_bus):
    """Test policy versioning tracker and rollback changes."""
    mgr = PolicyManager(event_bus=event_bus)
    
    # Register version 1.0.0
    p_v1 = {
        "policy_id": "pol-ver",
        "name": "Version 1",
        "version": "1.0.0",
        "category": "worker",
        "conditions": [],
        "effect": "allow",
        "priority": 1,
        "enabled": True
    }
    mgr.register(p_v1)
    
    # Register version 2.0.0
    p_v2 = p_v1.copy()
    p_v2["version"] = "2.0.0"
    p_v2["effect"] = "deny"
    mgr.register(p_v2)
    
    # Active version should be v2.0.0
    assert mgr.registry.get("pol-ver")["version"] == "2.0.0"
    assert mgr.evaluate("worker", {}) == "deny"
    
    # Rollback to v1.0.0
    rolled_version = mgr.rollback("pol-ver")
    assert rolled_version == "1.0.0"
    assert mgr.registry.get("pol-ver")["version"] == "1.0.0"
    assert mgr.evaluate("worker", {}) == "allow"
    assert event_bus.publish.called

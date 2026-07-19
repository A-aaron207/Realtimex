"""
Unit tests for the Realtimex Permission System.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from events.event import Event
from events.event_types import PermissionEventType
from permissions.exceptions import PermissionValidationError
from permissions.manager import PermissionManager
from permissions.persistence import PermissionPersistence
from permissions.policies import PermissionPolicy
from permissions.registry import SecurityManifest
from permissions.request import PermissionRequest
from permissions.decision import PermissionDecision



class DummyEventBus:
    """Mock event bus to collect emitted permission system events."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class DummyCognitiveEngine:
    """Mock cognitive engine evaluating security risks."""

    def __init__(self, risk_level: str = "low") -> None:
        self.risk_level = risk_level

    def reason(self, request: Any, decision_type: str) -> Any:
        # Mock CognitiveResponse object
        class MockResponse:
            def __init__(self, risk: str) -> None:
                self.recommendation = {"risk_level": risk}
                self.confidence = 0.95
                self.reasoning_summary = "Evaluated risk profile."

        return MockResponse(self.risk_level)


class TestPermissionSystem(unittest.TestCase):
    """Test cases verifying rule engines, policies, cache scopes, trust levels, and recovery."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persistence_path = Path(self.temp_dir.name)
        self.persistence = PermissionPersistence(directory=self.persistence_path)
        self.event_bus = DummyEventBus()
        self.cognitive_engine = DummyCognitiveEngine(risk_level="low")

        # Callback tracker
        self.reviewer_called = False
        self.reviewer_decision = True

        def reviewer(req: PermissionRequest) -> bool:
            self.reviewer_called = True
            return self.reviewer_decision

        self.user_reviewer = reviewer

        # Rule engine config: disable terminal execution by default, allow /workspace/* writes
        self.rule_args = {
            "deny_sudo": True,
            "allow_terminal_exec": False,
            "allowed_write_paths": ["/workspace/*"],
        }

        self.policy = PermissionPolicy(
            require_sudo_user_confirmation=True,
            read_only_mode=False,
            allowed_folders=["*"],
        )

        self.manager = PermissionManager(
            persistence=self.persistence,
            event_bus=self.event_bus,
            policy=self.policy,
            cognitive_engine=self.cognitive_engine,
            user_reviewer=self.user_reviewer,
            rule_engine_args=self.rule_args,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rule_engine_denials(self) -> None:
        """Verify Rule Engine blocks sudo, terminal_exec, and protected deletions."""
        # 1. Sudo
        dec_sudo = self.manager.request("t1", "worker-1", "sudo", "rm -rf /", "root_admin")
        self.assertFalse(dec_sudo.approved)
        self.assertEqual(dec_sudo.reviewer, "rule_engine")

        # 2. Terminal execution
        dec_exec = self.manager.request("t1", "worker-1", "terminal_exec", "python test.py", "exec")
        self.assertFalse(dec_exec.approved)

        # 3. Path write block (target not matching /workspace/*)
        dec_write = self.manager.request("t1", "worker-1", "file_write", "/etc/passwd", "write")
        self.assertFalse(dec_write.approved)

        # 4. Valid path write
        dec_write_ok = self.manager.request("t1", "worker-1", "file_write", "/workspace/src/app.py", "write")
        self.assertTrue(dec_write_ok.approved)

    def test_policy_evaluation_readonly(self) -> None:
        """Verify policy constraints like read_only_mode deny modifications."""
        self.manager.policy.read_only_mode = True

        # Write requested on whitelisted rule path, but blocked by higher level policy mode!
        dec = self.manager.request("t1", "worker-1", "file_write", "/workspace/src/app.py", "write")
        self.assertFalse(dec.approved)
        self.assertEqual(dec.reviewer, "policy_evaluator")

    def test_cognitive_analysis_risk_flagging(self) -> None:
        """Verify Cognitive Engine warnings trigger user confirmation requirements."""
        # Set cognitive engine to classify requests as high risk
        self.manager.cognitive_engine.risk_level = "high"

        # Ask to read file (normally default approved under rule path rules)
        dec = self.manager.request("t2", "worker-1", "file_read", "/workspace/rules.json", "read")
        
        # Should call user reviewer because cognitive engine flagged high risk!
        self.assertTrue(self.reviewer_called)
        self.assertTrue(dec.approved)
        self.assertEqual(dec.reviewer, "user")

    def test_trust_manager_review_trigger(self) -> None:
        """Verify untrusted entities trigger review, while trusted entities bypass it."""
        # Entity has low trust score (0.1)
        self.manager.set_trust_score("shady-worker", 0.1)

        # Low risk read file
        self.manager.request("t3", "shady-worker", "file_read", "/workspace/file.txt", "read")
        # Should trigger user reviewer because trust < 0.3
        self.assertTrue(self.reviewer_called)

        # Reset callback trackers
        self.reviewer_called = False
        
        # Entity has high trust score (0.9)
        self.manager.set_trust_score("trusted-worker", 0.9)
        self.manager.request("t3", "trusted-worker", "file_read", "/workspace/file.txt", "read")
        # High trust + low risk should bypass user reviewer!
        self.assertFalse(self.reviewer_called)

    def test_sandboxing_predeclarations(self) -> None:
        """Verify registry security manifests enforce sandboxed declarations."""
        manifest = SecurityManifest(
            entity_id="sandboxed-worker",
            allowed_actions=["file_read"],
            allowed_targets=["/workspace/safe/*"],
        )
        self.manager.registry.register_manifest(manifest)

        # 1. Allowed action & target matches glob
        dec_ok = self.manager.request("t4", "sandboxed-worker", "file_read", "/workspace/safe/data.json", "read")
        self.assertTrue(dec_ok.approved)

        # 2. Target outside manifest glob patterns
        dec_bad_target = self.manager.request("t4", "sandboxed-worker", "file_read", "/workspace/secrets.txt", "read")
        self.assertFalse(dec_bad_target.approved)

        # 3. Action not in declared allowed actions
        dec_bad_action = self.manager.request("t4", "sandboxed-worker", "file_write", "/workspace/safe/data.json", "write")
        self.assertFalse(dec_bad_action.approved)

    def test_caching_and_expiration(self) -> None:
        """Verify cache expiration, task scopes, and once-use evictions."""
        req = PermissionRequest(
            task_id="task-cache",
            worker_id="worker-c",
            action="file_read",
            target="/workspace/cached.txt",
            requested_capability="read",
        )

        # 1. Once Cache Policy: evicted after single read
        dec_once = PermissionDecision(approved=True, reason="ok", reviewer="user", cache_policy="once")
        self.manager.cache(req, dec_once)
        
        # First query gets it
        self.assertTrue(self.manager.request("task-cache", "worker-c", "file_read", "/workspace/cached.txt", "read").approved)
        # Second query should re-evaluate (cache miss) since once evicted
        self.reviewer_called = False
        self.manager.set_trust_score("worker-c", 0.1) # force review to verify it does not hit cache
        self.manager.request("task-cache", "worker-c", "file_read", "/workspace/cached.txt", "read")
        self.assertTrue(self.reviewer_called)

        # 2. Task Cache Policy: evicted on task invalidation
        self.reviewer_called = False
        dec_task = PermissionDecision(approved=True, reason="ok", reviewer="user", cache_policy="task")
        self.manager.cache(req, dec_task)
        
        # Hits cache (no reviewer called)
        self.manager.request("task-cache", "worker-c", "file_read", "/workspace/cached.txt", "read")
        self.assertFalse(self.reviewer_called)

        # Invalidate task
        self.manager.cache_store.invalidate_task("task-cache")
        # Triggers review now (cache miss)
        self.manager.request("task-cache", "worker-c", "file_read", "/workspace/cached.txt", "read")
        self.assertTrue(self.reviewer_called)

    def test_state_persistence_recovery(self) -> None:
        """Verify trust levels and persistent approvals recover after manager restarts."""
        # 1. Setup trust and persistent approval
        self.manager.set_trust_score("agent-alpha", 0.85)

        req = PermissionRequest(
            task_id="t-persist",
            worker_id="agent-alpha",
            action="file_read",
            target="/workspace/important.txt",
            requested_capability="read",
        )
        dec = PermissionDecision(
            approved=True,
            reason="approved persistently",
            reviewer="user",
            cache_policy="persistent",
        )
        # Manually cache it so it persists to disk
        self.manager.cache(req, dec)

        # 2. Spin up a new manager sharing the same persistence directory
        manager2 = PermissionManager(
            persistence=self.persistence,
            user_reviewer=self.user_reviewer,
        )

        # Trust score recovered
        self.assertEqual(manager2.trust_manager.get_trust_score("agent-alpha"), 0.85)

        # Persistent approval cache recovered
        dec_recovered = manager2.request("t-persist", "agent-alpha", "file_read", "/workspace/important.txt", "read")
        self.assertTrue(dec_recovered.approved)
        self.assertEqual(dec_recovered.reviewer, "user")


if __name__ == "__main__":
    unittest.main()

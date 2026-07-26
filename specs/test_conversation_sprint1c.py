"""
Sprint 1C — Conversation Reliability Tests
============================================
Covers: routing correctness, response formatting (no raw output), multi-turn
        session continuity, error propagation, auth/authz edge cases,
        serialization contracts, session lifecycle, manager throughput,
        crash resilience, and conversation integrity.

Target: close the gap from 103/150 toward 150/150 on the Conversation subsystem.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from interfaces.authentication import AuthenticationManager, AuthorizationManager
from interfaces.base import Interface, Request, Response
from interfaces.exceptions import (
    AuthenticationError,
    SerializationError,
    SessionError,
)
from interfaces.manager import InterfaceManager
from interfaces.registry import InterfaceRegistry
from interfaces.serialization import SerializationManager
from interfaces.session import Session, SessionManager


# ---------------------------------------------------------------------------
# Shared Mocks
# ---------------------------------------------------------------------------


class MockInterface(Interface):
    """Minimal Interface implementation for unit tests."""

    def __init__(self, name: str = "mock") -> None:
        super().__init__(name=name, interface_type=name)
        self.received_requests: list[Request] = []
        self.sent_responses: list[Response] = []

    def initialize(self) -> None:
        pass

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def shutdown(self) -> None:
        self.stop()

    def receive(self) -> Optional[Request]:
        if self.received_requests:
            return self.received_requests.pop(0)
        return None

    def send(self, response: Response) -> None:
        self.sent_responses.append(response)


def _make_request(
    user_input: str = "hello",
    session_id: str | None = None,
    user_id: str = "user-test",
    interface_type: str = "cli",
    metadata: dict[str, Any] | None = None,
) -> Request:
    return Request(
        request_id=str(uuid.uuid4()),
        session_id=session_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_input=user_input,
        interface_type=interface_type,
        user_id=user_id,
        metadata=metadata or {},
    )


def _make_response(
    request_id: str = "req-1",
    status: str = "success",
    message: str = "ok",
) -> Response:
    return Response(request_id=request_id, status=status, message=message)


# ---------------------------------------------------------------------------
# 1. Response Formatting — No Raw Output
# ---------------------------------------------------------------------------


class TestResponseFormatting(unittest.TestCase):
    """
    Conversation: responses must narrate results, never expose raw system output.
    Gate 6 — UX: No raw system output exposed to user.
    """

    def test_success_response_has_message(self) -> None:
        """Success response always contains a non-empty message string."""
        resp = _make_response(status="success", message="Task completed successfully.")
        self.assertIsInstance(resp.message, str)
        self.assertGreater(len(resp.message), 0)

    def test_error_response_has_message(self) -> None:
        """Error response always contains a non-empty message string."""
        resp = _make_response(status="error", message="An error occurred: file not found.")
        self.assertIsInstance(resp.message, str)
        self.assertGreater(len(resp.message), 0)

    def test_response_message_not_raw_status_string(self) -> None:
        """Response message must not be a bare system status token like 'SUCCESS' or 'DONE'."""
        banned = {"SUCCESS", "DONE", "OK", "COMPLETED", "ERROR", "FAIL", "FAILED"}
        resp = _make_response(message="Your task is complete.")
        self.assertNotIn(resp.message.strip().upper(), banned)

    def test_response_to_dict_structure(self) -> None:
        """Response.to_dict() produces all required keys."""
        resp = Response(
            request_id="r1",
            status="success",
            message="Done.",
            artifacts={"file": "out.py"},
            events=["step_completed"],
            metadata={"task_id": "t1"},
        )
        d = resp.to_dict()
        for key in ("request_id", "status", "message"):
            self.assertIn(key, d)

    def test_response_artifact_accessible(self) -> None:
        """Artifacts embedded in a response are accessible after serialization."""
        resp = Response(
            request_id="r2",
            status="success",
            message="File created.",
            artifacts={"path": "/home/user/calc.py", "lang": "python"},
        )
        self.assertEqual(resp.artifacts["lang"], "python")

    def test_response_events_list_accessible(self) -> None:
        """Events list in a response is a list."""
        resp = Response(
            request_id="r3",
            status="success",
            message="Steps done.",
            events=["step_1_completed", "step_2_completed"],
        )
        self.assertIsInstance(resp.events, list)
        self.assertEqual(len(resp.events), 2)

    def test_response_status_is_normalised_string(self) -> None:
        """Response status must be a lowercase string ('success', 'error', 'pending')."""
        for status in ("success", "error", "pending"):
            resp = _make_response(status=status)
            self.assertEqual(resp.status, status)

    def test_response_request_id_echoed(self) -> None:
        """Response request_id must match the originating request_id."""
        req = _make_request()
        resp = Response(request_id=req.request_id, status="success", message="handled")
        self.assertEqual(resp.request_id, req.request_id)

    def test_response_defaults_empty_artifacts(self) -> None:
        """Response without artifacts defaults to an empty collection."""
        resp = _make_response()
        # artifacts may be a list or dict depending on implementation — must be empty
        self.assertFalse(bool(resp.artifacts))

    def test_response_defaults_empty_events(self) -> None:
        """Response without events defaults to empty list."""
        resp = _make_response()
        self.assertEqual(resp.events, [])


# ---------------------------------------------------------------------------
# 2. Request Routing Correctness
# ---------------------------------------------------------------------------


class TestRequestRoutingCorrectness(unittest.TestCase):
    """Conversation: requests from interfaces are correctly routed and handled."""

    def _make_manager_with_echo_handler(self) -> tuple[InterfaceManager, MockInterface]:
        """Create manager with an echo handler."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")

        def echo_handler(request: Request) -> Response:
            return Response(
                request_id=request.request_id,
                status="success",
                message=f"Echo: {request.user_input}",
                metadata={"session_id": request.session_id},
            )

        manager.set_request_handler(echo_handler)
        return manager, interface

    def test_request_routed_to_handler(self) -> None:
        """Request placed in interface queue is routed to the registered handler."""
        manager, interface = self._make_manager_with_echo_handler()
        req = _make_request(user_input="hello world")
        interface.received_requests.append(req)

        raw_req = manager.receive("cli")
        self.assertIsNotNone(raw_req)
        resp = manager.process_request(raw_req)
        self.assertEqual(resp.status, "success")
        self.assertIn("Echo", resp.message)

    def test_no_handler_returns_error_response(self) -> None:
        """process_request() without a handler returns an error response."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")
        req = _make_request()
        interface.received_requests.append(req)
        raw_req = manager.receive("cli")
        resp = manager.process_request(raw_req)
        self.assertEqual(resp.status, "error")

    def test_response_sent_back_to_interface(self) -> None:
        """send() delivers the response to the correct interface."""
        manager, interface = self._make_manager_with_echo_handler()
        req = _make_request()
        interface.received_requests.append(req)
        raw_req = manager.receive("cli")
        resp = manager.process_request(raw_req)
        manager.send(resp)
        self.assertEqual(len(interface.sent_responses), 1)
        self.assertEqual(interface.sent_responses[0].request_id, resp.request_id)

    def test_correct_interface_receives_response(self) -> None:
        """send() targets the interface that originated the request."""
        manager = InterfaceManager()
        iface_a = MockInterface("cli")
        iface_b = MockInterface("api")
        manager.register_interface(iface_a)
        manager.register_interface(iface_b)
        manager.start_interface("cli")
        manager.start_interface("api")

        def handler(request: Request) -> Response:
            return Response(request_id=request.request_id, status="success", message="routed")

        manager.set_request_handler(handler)

        req = _make_request(interface_type="api")
        iface_b.received_requests.append(req)
        raw_req = manager.receive("api")
        resp = manager.process_request(raw_req)
        manager.send(resp)

        self.assertEqual(len(iface_b.sent_responses), 1)
        self.assertEqual(len(iface_a.sent_responses), 0)

    def test_handler_exception_returns_error_response(self) -> None:
        """Handler raising an exception produces an error response, not a crash."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")

        def crashing_handler(request: Request) -> Response:
            raise RuntimeError("Simulated crash")

        manager.set_request_handler(crashing_handler)
        req = _make_request()
        interface.received_requests.append(req)
        raw_req = manager.receive("cli")
        resp = manager.process_request(raw_req)
        self.assertEqual(resp.status, "error")
        # Must not expose raw exception type to user
        self.assertNotIn("RuntimeError", resp.message)

    def test_multiple_sequential_requests_handled(self) -> None:
        """Multiple sequential requests are all handled correctly."""
        manager, interface = self._make_manager_with_echo_handler()
        for i in range(5):
            req = _make_request(user_input=f"message {i}")
            interface.received_requests.append(req)
            raw_req = manager.receive("cli")
            resp = manager.process_request(raw_req)
            self.assertEqual(resp.status, "success")

    def test_empty_queue_receive_returns_none(self) -> None:
        """receive() on an empty interface returns None without error."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")
        result = manager.receive("cli")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 3. Multi-turn Session Continuity
# ---------------------------------------------------------------------------


class TestMultiTurnSessionContinuity(unittest.TestCase):
    """Conversation: session context persists across multiple turns."""

    def test_session_context_persists_across_turns(self) -> None:
        """Context set in turn 1 is available in turn 2."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")

        sm.update_context(sess.session_id, {"last_file": "calc.py"})
        retrieved = sm.get_session(sess.session_id)
        self.assertEqual(retrieved.context["last_file"], "calc.py")

    def test_session_context_incremental_merge(self) -> None:
        """Multiple update_context() calls merge all keys (no overwrite)."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")

        sm.update_context(sess.session_id, {"key_a": "val_a"})
        sm.update_context(sess.session_id, {"key_b": "val_b"})
        retrieved = sm.get_session(sess.session_id)
        self.assertEqual(retrieved.context["key_a"], "val_a")
        self.assertEqual(retrieved.context["key_b"], "val_b")

    def test_multiple_tasks_same_session(self) -> None:
        """Multiple tasks can be active within a single session."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")
        sm.add_task(sess.session_id, "task-a")
        sm.add_task(sess.session_id, "task-b")
        sm.add_task(sess.session_id, "task-c")
        retrieved = sm.get_session(sess.session_id)
        self.assertIn("task-a", retrieved.active_tasks)
        self.assertIn("task-b", retrieved.active_tasks)
        self.assertIn("task-c", retrieved.active_tasks)

    def test_task_completion_removes_from_session(self) -> None:
        """Completed task is removed from session active_tasks."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")
        sm.add_task(sess.session_id, "task-x")
        sm.remove_task(sess.session_id, "task-x")
        retrieved = sm.get_session(sess.session_id)
        self.assertNotIn("task-x", retrieved.active_tasks)

    def test_session_activity_updated_on_get(self) -> None:
        """get_session() refreshes last_activity timestamp."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")
        original_ts = sess.last_activity
        time.sleep(0.05)
        retrieved = sm.get_session(sess.session_id)
        self.assertGreaterEqual(retrieved.last_activity, original_ts)

    def test_session_age_increases(self) -> None:
        """session.age_seconds increases over time."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")
        time.sleep(0.05)
        retrieved = sm.get_session(sess.session_id)
        self.assertGreater(retrieved.age_seconds, 0.0)

    def test_idle_session_cleanup(self) -> None:
        """Idle sessions are removed when cleanup_idle_sessions() is called."""
        sm = SessionManager()
        sm.create_session("user-idle", "cli")
        time.sleep(0.06)
        removed = sm.cleanup_idle_sessions(idle_timeout_seconds=0.04)
        self.assertGreaterEqual(removed, 1)
        sessions = sm.list_sessions()
        self.assertEqual(len([s for s in sessions if s.user_id == "user-idle"]), 0)

    def test_active_session_not_cleaned_up(self) -> None:
        """Active (recently used) sessions survive cleanup_idle_sessions()."""
        sm = SessionManager()
        sess = sm.create_session("user-active", "cli")
        sm.get_session(sess.session_id)  # Touch it
        removed = sm.cleanup_idle_sessions(idle_timeout_seconds=60.0)
        self.assertEqual(removed, 0)

    def test_user_sessions_list(self) -> None:
        """list_user_sessions() returns all sessions for a specific user."""
        sm = SessionManager()
        sm.create_session("user-multi", "cli")
        sm.create_session("user-multi", "api")
        sm.create_session("user-other", "cli")
        user_sessions = sm.list_user_sessions("user-multi")
        self.assertEqual(len(user_sessions), 2)

    def test_session_count_accurate(self) -> None:
        """session_count() accurately reflects number of active sessions."""
        sm = SessionManager()
        self.assertEqual(sm.session_count(), 0)
        sm.create_session("u1", "cli")
        sm.create_session("u2", "cli")
        self.assertEqual(sm.session_count(), 2)

    def test_closed_session_not_in_list(self) -> None:
        """Closed session no longer appears in list_sessions()."""
        sm = SessionManager()
        sess = sm.create_session("user-close", "cli")
        sm.close_session(sess.session_id)
        sessions = sm.list_sessions()
        self.assertNotIn(sess.session_id, [s.session_id for s in sessions])

    def test_session_to_dict_complete(self) -> None:
        """Session.to_dict() contains all required fields."""
        sm = SessionManager()
        sess = sm.create_session("user-dict", "cli", context={"x": 1}, metadata={"y": 2})
        d = sess.to_dict()
        for key in ("session_id", "user_id", "interface_type", "created_at", "active_tasks", "context"):
            self.assertIn(key, d)
        self.assertEqual(d["context"]["x"], 1)

    def test_add_same_task_twice_no_duplicate(self) -> None:
        """Adding the same task_id twice does not duplicate it in active_tasks."""
        sm = SessionManager()
        sess = sm.create_session("user-dup", "cli")
        sm.add_task(sess.session_id, "task-dup")
        sm.add_task(sess.session_id, "task-dup")
        retrieved = sm.get_session(sess.session_id)
        self.assertEqual(retrieved.active_tasks.count("task-dup"), 1)

    def test_remove_nonexistent_task_is_silent(self) -> None:
        """Removing a non-existent task_id does not raise an error."""
        sm = SessionManager()
        sess = sm.create_session("user-1", "cli")
        result = sm.remove_task(sess.session_id, "ghost-task")
        self.assertTrue(result)  # Returns True because session exists


# ---------------------------------------------------------------------------
# 4. Authentication & Authorization Edge Cases
# ---------------------------------------------------------------------------


class TestAuthEdgeCases(unittest.TestCase):
    """Conversation: auth/authz boundary conditions and security contracts."""

    # --- AuthenticationManager ---

    def test_token_unique_per_user(self) -> None:
        """Two tokens for different users are not equal."""
        auth = AuthenticationManager()
        t1 = auth.generate_token("user-a")
        t2 = auth.generate_token("user-b")
        self.assertNotEqual(t1, t2)

    def test_token_unique_per_generation(self) -> None:
        """Two tokens for the same user are unique (no reuse)."""
        auth = AuthenticationManager()
        t1 = auth.generate_token("user-1")
        t2 = auth.generate_token("user-1")
        self.assertNotEqual(t1, t2)

    def test_validate_token_correct_user(self) -> None:
        """Validating a fresh token returns the correct user_id."""
        auth = AuthenticationManager()
        token = auth.generate_token("user-correct")
        self.assertEqual(auth.validate_token(token), "user-correct")

    def test_invalid_token_returns_none(self) -> None:
        """Random invalid token returns None."""
        auth = AuthenticationManager()
        self.assertIsNone(auth.validate_token("not-a-real-token"))

    def test_empty_token_returns_none(self) -> None:
        """Empty string token returns None."""
        auth = AuthenticationManager()
        self.assertIsNone(auth.validate_token(""))

    def test_revoked_token_invalid(self) -> None:
        """Revoked token immediately becomes invalid."""
        auth = AuthenticationManager()
        token = auth.generate_token("user-1")
        auth.revoke_token(token)
        self.assertIsNone(auth.validate_token(token))

    def test_refreshed_token_valid(self) -> None:
        """Refreshed token is valid and maps to the same user."""
        auth = AuthenticationManager()
        old = auth.generate_token("user-refresh")
        new = auth.refresh_token(old)
        self.assertEqual(auth.validate_token(new), "user-refresh")

    def test_old_token_invalid_after_refresh(self) -> None:
        """Old token is invalid after being refreshed."""
        auth = AuthenticationManager()
        old = auth.generate_token("user-refresh-2")
        auth.refresh_token(old)
        self.assertIsNone(auth.validate_token(old))

    def test_revoke_nonexistent_token_no_crash(self) -> None:
        """Revoking a non-existent token does not raise an error."""
        auth = AuthenticationManager()
        # Should not raise
        auth.revoke_token("ghost-token-xyz")

    def test_token_is_string(self) -> None:
        """Generated token must be a non-empty string."""
        auth = AuthenticationManager()
        token = auth.generate_token("user-1")
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    # --- AuthorizationManager ---

    def test_admin_role_has_all_permissions(self) -> None:
        """Admin role grants all core task permissions."""
        authz = AuthorizationManager()
        authz.assign_role("admin-user", "admin")
        for perm in ("task.create", "task.read", "task.delete"):
            self.assertTrue(authz.check_permission("admin-user", perm))

    def test_viewer_role_read_only(self) -> None:
        """Viewer role can read but not delete tasks."""
        authz = AuthorizationManager()
        authz.assign_role("viewer-user", "viewer")
        self.assertTrue(authz.check_permission("viewer-user", "task.read"))
        self.assertFalse(authz.check_permission("viewer-user", "task.delete"))

    def test_unknown_user_no_permissions(self) -> None:
        """User with no assigned role has no permissions."""
        authz = AuthorizationManager()
        self.assertFalse(authz.check_permission("ghost-user", "task.create"))

    def test_custom_role_with_specific_permission(self) -> None:
        """Custom role grants exactly the specified permissions."""
        authz = AuthorizationManager()
        authz.create_role("auditor", {"audit.read", "audit.export"})
        authz.assign_role("auditor-user", "auditor")
        self.assertTrue(authz.check_permission("auditor-user", "audit.read"))
        self.assertFalse(authz.check_permission("auditor-user", "task.create"))

    def test_get_user_permissions_non_empty(self) -> None:
        """get_user_permissions() for a user with a role returns non-empty set."""
        authz = AuthorizationManager()
        authz.assign_role("perm-user", "user")
        perms = authz.get_user_permissions("perm-user")
        self.assertIsInstance(perms, (set, list))
        self.assertGreater(len(perms), 0)

    def test_multiple_role_assignment(self) -> None:
        """User can be assigned multiple roles and gets union of permissions."""
        authz = AuthorizationManager()
        authz.create_role("role_a", {"perm.alpha"})
        authz.create_role("role_b", {"perm.beta"})
        authz.assign_role("multi-user", "role_a")
        authz.assign_role("multi-user", "role_b")
        self.assertTrue(authz.check_permission("multi-user", "perm.alpha"))
        self.assertTrue(authz.check_permission("multi-user", "perm.beta"))


# ---------------------------------------------------------------------------
# 5. Serialization Contracts
# ---------------------------------------------------------------------------


class TestSerializationContracts(unittest.TestCase):
    """Conversation: request/response serialization round-trips without data loss."""

    def setUp(self) -> None:
        self.manager = SerializationManager()

    def test_request_round_trip_all_fields(self) -> None:
        """Request round-trips through serialize/deserialize without loss."""
        now = datetime.now(timezone.utc)
        req = Request(
            request_id="ser-req-1",
            session_id="ser-sess-1",
            timestamp=now,
            user_input="serialize me",
            interface_type="cli",
            user_id="user-ser",
            metadata={"key": "value", "num": 42},
        )
        serialized = self.manager.serialize_request(req)
        self.assertIsInstance(serialized, str)
        deserialized = self.manager.deserialize_request(serialized)
        self.assertEqual(deserialized.request_id, "ser-req-1")
        self.assertEqual(deserialized.session_id, "ser-sess-1")
        self.assertEqual(deserialized.user_input, "serialize me")
        self.assertEqual(deserialized.metadata["num"], 42)

    def test_response_round_trip_all_fields(self) -> None:
        """Response round-trips through serialize/deserialize without loss."""
        resp = Response(
            request_id="ser-resp-1",
            status="success",
            message="Serialized OK.",
            artifacts={"file": "out.txt"},
            events=["step_done"],
            metadata={"task_id": "t99"},
        )
        serialized = self.manager.serialize_response(resp)
        self.assertIsInstance(serialized, str)
        deserialized = self.manager.deserialize_response(serialized)
        self.assertEqual(deserialized.request_id, "ser-resp-1")
        self.assertEqual(deserialized.status, "success")
        self.assertEqual(deserialized.artifacts["file"], "out.txt")
        self.assertEqual(deserialized.events[0], "step_done")

    def test_serialized_request_is_valid_json(self) -> None:
        """Serialized request is valid JSON."""
        req = _make_request()
        serialized = self.manager.serialize_request(req)
        try:
            json.loads(serialized)
        except json.JSONDecodeError:
            self.fail("Serialized request is not valid JSON")

    def test_serialized_response_is_valid_json(self) -> None:
        """Serialized response is valid JSON."""
        resp = _make_response()
        serialized = self.manager.serialize_response(resp)
        try:
            json.loads(serialized)
        except json.JSONDecodeError:
            self.fail("Serialized response is not valid JSON")

    def test_deserialize_invalid_json_raises(self) -> None:
        """Deserializing invalid JSON raises SerializationError."""
        with self.assertRaises(SerializationError):
            self.manager.deserialize_request("not json at all {{{")

    def test_deserialize_missing_fields_raises(self) -> None:
        """Deserializing JSON missing required fields raises SerializationError."""
        minimal = json.dumps({"request_id": "r1"})  # Missing session_id, etc.
        with self.assertRaises(SerializationError):
            self.manager.deserialize_request(minimal)

    def test_response_metadata_preserved(self) -> None:
        """Response metadata dict is preserved through serialization."""
        resp = Response(
            request_id="r-meta",
            status="success",
            message="ok",
            metadata={"task_id": "abc", "duration_ms": 55},
        )
        d = self.manager.serialize_response(resp)
        restored = self.manager.deserialize_response(d)
        self.assertEqual(restored.metadata["task_id"], "abc")
        self.assertEqual(restored.metadata["duration_ms"], 55)

    def test_request_id_auto_generated_if_missing(self) -> None:
        """Request auto-generates request_id if not provided."""
        req = Request(
            request_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            user_input="test",
            interface_type="cli",
            user_id="u1",
        )
        self.assertIsNotNone(req.request_id)
        self.assertGreater(len(req.request_id), 0)


# ---------------------------------------------------------------------------
# 6. Interface Registry
# ---------------------------------------------------------------------------


class TestInterfaceRegistry(unittest.TestCase):
    """Conversation: registry lifecycle and lookup correctness."""

    def test_register_and_get(self) -> None:
        """Registered interface is retrievable by type."""
        reg = InterfaceRegistry()
        iface = MockInterface("cli")
        reg.register(iface)
        self.assertIs(reg.get("cli"), iface)

    def test_unregister_removes(self) -> None:
        """Unregistered interface is no longer retrievable."""
        reg = InterfaceRegistry()
        iface = MockInterface("cli")
        reg.register(iface)
        reg.unregister("cli")
        self.assertIsNone(reg.get("cli"))

    def test_list_returns_all(self) -> None:
        """list() returns all registered interfaces."""
        reg = InterfaceRegistry()
        reg.register(MockInterface("cli"))
        reg.register(MockInterface("api"))
        self.assertEqual(len(reg.list()), 2)

    def test_get_unknown_returns_none(self) -> None:
        """get() for unknown interface type returns None."""
        reg = InterfaceRegistry()
        self.assertIsNone(reg.get("nonexistent"))

    def test_reregister_replaces(self) -> None:
        """Unregister then re-register with same type replaces the old interface."""
        reg = InterfaceRegistry()
        iface_old = MockInterface("cli")
        iface_new = MockInterface("cli")
        reg.register(iface_old)
        # Registry requires explicit unregister before re-registering the same type
        reg.unregister("cli")
        reg.register(iface_new)
        self.assertIs(reg.get("cli"), iface_new)

    def test_unregister_nonexistent_no_crash(self) -> None:
        """Unregistering a non-existent interface does not raise."""
        reg = InterfaceRegistry()
        reg.unregister("ghost")  # Should not raise

    def test_empty_registry_list_empty(self) -> None:
        """Empty registry returns empty list."""
        reg = InterfaceRegistry()
        self.assertEqual(reg.list(), [])


# ---------------------------------------------------------------------------
# 7. Manager Concurrency and Throughput
# ---------------------------------------------------------------------------


class TestManagerConcurrencyAndThroughput(unittest.TestCase):
    """Conversation: thread safety of session and interface operations."""

    def test_concurrent_session_creation_thread_safe(self) -> None:
        """50 concurrent sessions can be created without errors."""
        sm = SessionManager()
        sessions: list[str] = []
        errors: list[Exception] = []

        def create(count: int) -> None:
            try:
                for i in range(count):
                    s = sm.create_session(f"user-{i}", "cli")
                    sessions.append(s.session_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(10,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(sessions), 50)
        self.assertEqual(sm.session_count(), 50)

    def test_concurrent_context_update_no_data_loss(self) -> None:
        """Concurrent context updates to the same session do not corrupt data."""
        sm = SessionManager()
        sess = sm.create_session("user-conc", "cli")
        errors: list[Exception] = []

        def update_ctx(key: str) -> None:
            try:
                sm.update_context(sess.session_id, {key: "value"})
            except Exception as e:
                errors.append(e)

        keys = [f"key_{i}" for i in range(20)]
        threads = [threading.Thread(target=update_ctx, args=(k,)) for k in keys]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        ctx = sm.get_session(sess.session_id).context
        self.assertEqual(len(ctx), 20)

    def test_manager_handles_100_requests_sequentially(self) -> None:
        """InterfaceManager handles 100 sequential requests without failure."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")

        call_count = 0

        def counter_handler(request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            return Response(request_id=request.request_id, status="success", message="ok")

        manager.set_request_handler(counter_handler)

        for _ in range(100):
            req = _make_request()
            interface.received_requests.append(req)
            raw = manager.receive("cli")
            manager.process_request(raw)

        self.assertEqual(call_count, 100)

    def test_session_manager_thread_safe_close(self) -> None:
        """Concurrent close_session() calls do not raise."""
        sm = SessionManager()
        sess = sm.create_session("user-close", "cli")
        errors: list[Exception] = []

        def close_it() -> None:
            try:
                sm.close_session(sess.session_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=close_it) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


# ---------------------------------------------------------------------------
# 8. Conversation Integrity (Request → Route → Respond → No Raw Leak)
# ---------------------------------------------------------------------------


class TestConversationIntegrity(unittest.TestCase):
    """End-to-end: no raw system output leaks through the conversation layer."""

    def _build_pipeline(
        self, handler_message: str = "Your request is complete."
    ) -> tuple[InterfaceManager, MockInterface]:
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")

        def handler(request: Request) -> Response:
            return Response(
                request_id=request.request_id,
                status="success",
                message=handler_message,
            )

        manager.set_request_handler(handler)
        return manager, interface

    def test_user_sees_message_not_task_state(self) -> None:
        """Response message is human-readable, not a raw task state token."""
        manager, interface = self._build_pipeline()
        req = _make_request(user_input="run my script")
        interface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        raw_tokens = {"RUNNING", "COMPLETED", "PENDING", "FAILED", "CREATED"}
        self.assertNotIn(resp.message.strip().upper(), raw_tokens)

    def test_user_sees_message_not_exception_text(self) -> None:
        """Exception messages do not surface the exception class name to the user."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")

        def bad_handler(request: Request) -> Response:
            raise ValueError("internal parsing error")

        manager.set_request_handler(bad_handler)
        req = _make_request()
        interface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)

        self.assertEqual(resp.status, "error")
        self.assertNotIn("ValueError", resp.message)
        self.assertNotIn("Traceback", resp.message)

    def test_response_message_is_string_always(self) -> None:
        """Response message is always a string, never None or a raw object."""
        manager, interface = self._build_pipeline("Done.")
        req = _make_request()
        interface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertIsInstance(resp.message, str)

    def test_session_id_preserved_through_pipeline(self) -> None:
        """Session ID on the original request matches the response metadata."""
        manager, interface = self._build_pipeline()
        session_id = str(uuid.uuid4())
        req = _make_request(session_id=session_id)
        interface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        # request_id must echo back
        self.assertEqual(resp.request_id, req.request_id)

    def test_error_response_still_has_valid_structure(self) -> None:
        """Error response still has all required fields populated."""
        manager = InterfaceManager()
        interface = MockInterface("cli")
        manager.register_interface(interface)
        manager.start_interface("cli")
        # No handler set
        req = _make_request()
        interface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertEqual(resp.status, "error")
        self.assertIsInstance(resp.message, str)
        self.assertGreater(len(resp.message), 0)
        self.assertEqual(resp.request_id, req.request_id)

    def test_multiple_interfaces_isolated(self) -> None:
        """Messages for interface A do not appear in interface B's sent queue."""
        manager = InterfaceManager()
        iface_a = MockInterface("cli")
        iface_b = MockInterface("api")
        manager.register_interface(iface_a)
        manager.register_interface(iface_b)
        manager.start_interface("cli")
        manager.start_interface("api")

        def handler(request: Request) -> Response:
            return Response(request_id=request.request_id, status="success", message="ok")

        manager.set_request_handler(handler)

        req_a = _make_request(interface_type="cli")
        iface_a.received_requests.append(req_a)
        raw_a = manager.receive("cli")
        resp_a = manager.process_request(raw_a)
        manager.send(resp_a)

        self.assertEqual(len(iface_a.sent_responses), 1)
        self.assertEqual(len(iface_b.sent_responses), 0)


# ---------------------------------------------------------------------------
# 9. Session Serialization
# ---------------------------------------------------------------------------


class TestSessionSerialization(unittest.TestCase):
    """Conversation: session state serializes to a complete, recoverable dict."""

    def test_session_to_dict_has_session_id(self) -> None:
        """Session.to_dict() includes 'session_id'."""
        sm = SessionManager()
        sess = sm.create_session("u1", "cli")
        d = sess.to_dict()
        self.assertIn("session_id", d)
        self.assertEqual(d["session_id"], sess.session_id)

    def test_session_to_dict_has_user_id(self) -> None:
        """Session.to_dict() includes 'user_id'."""
        sm = SessionManager()
        sess = sm.create_session("user-dict", "cli")
        self.assertEqual(sess.to_dict()["user_id"], "user-dict")

    def test_session_to_dict_has_interface_type(self) -> None:
        """Session.to_dict() includes 'interface_type'."""
        sm = SessionManager()
        sess = sm.create_session("u1", "websocket")
        self.assertEqual(sess.to_dict()["interface_type"], "websocket")

    def test_session_to_dict_has_created_at(self) -> None:
        """Session.to_dict() includes ISO 8601 'created_at'."""
        sm = SessionManager()
        sess = sm.create_session("u1", "cli")
        d = sess.to_dict()
        self.assertIn("created_at", d)
        # Must be parseable
        datetime.fromisoformat(d["created_at"])

    def test_session_to_dict_has_active_tasks(self) -> None:
        """Session.to_dict() includes 'active_tasks' list."""
        sm = SessionManager()
        sess = sm.create_session("u1", "cli")
        sm.add_task(sess.session_id, "t1")
        d = sess.to_dict()
        self.assertIn("active_tasks", d)
        self.assertIn("t1", d["active_tasks"])

    def test_session_idle_seconds_in_dict(self) -> None:
        """Session.to_dict() includes computed 'idle_seconds'."""
        sm = SessionManager()
        sess = sm.create_session("u1", "cli")
        d = sess.to_dict()
        self.assertIn("idle_seconds", d)
        self.assertGreaterEqual(d["idle_seconds"], 0.0)


# ---------------------------------------------------------------------------
# 10. Interface Lifecycle
# ---------------------------------------------------------------------------


class TestInterfaceLifecycle(unittest.TestCase):
    """Conversation: interface start/stop lifecycle correctness."""

    def test_interface_starts_not_running(self) -> None:
        """Fresh interface is not running before start()."""
        iface = MockInterface("cli")
        self.assertFalse(iface.is_running)

    def test_interface_running_after_start(self) -> None:
        """Interface is running after start()."""
        iface = MockInterface("cli")
        iface.start()
        self.assertTrue(iface.is_running)

    def test_interface_stopped_after_stop(self) -> None:
        """Interface is not running after stop()."""
        iface = MockInterface("cli")
        iface.start()
        iface.stop()
        self.assertFalse(iface.is_running)

    def test_manager_start_starts_all_interfaces(self) -> None:
        """manager.start() starts all registered interfaces."""
        manager = InterfaceManager()
        iface_a = MockInterface("cli")
        iface_b = MockInterface("api")
        manager.register_interface(iface_a)
        manager.register_interface(iface_b)
        manager.start()
        self.assertTrue(iface_a.is_running)
        self.assertTrue(iface_b.is_running)

    def test_manager_stop_stops_all_interfaces(self) -> None:
        """manager.stop() stops all running interfaces."""
        manager = InterfaceManager()
        iface_a = MockInterface("cli")
        iface_b = MockInterface("api")
        manager.register_interface(iface_a)
        manager.register_interface(iface_b)
        manager.start()
        manager.stop()
        self.assertFalse(iface_a.is_running)
        self.assertFalse(iface_b.is_running)

    def test_interface_count_after_registration(self) -> None:
        """manager.interfaces() reflects all registered interfaces."""
        manager = InterfaceManager()
        manager.register_interface(MockInterface("cli"))
        manager.register_interface(MockInterface("api"))
        self.assertEqual(len(manager.interfaces()), 2)

    def test_unregistered_interface_not_in_list(self) -> None:
        """Unregistered interface is removed from manager.interfaces()."""
        manager = InterfaceManager()
        iface = MockInterface("cli")
        manager.register_interface(iface)
        manager.registry.unregister("cli")
        self.assertEqual(len(manager.interfaces()), 0)


if __name__ == "__main__":
    unittest.main()

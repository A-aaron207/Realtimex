"""
Regression Test: Issue #48 — process_request() Crashes When No Handler Set
===========================================================================
Root Cause:
    InterfaceManager.process_request() raised InterfaceManagerError when called
    with no request handler set. This propagated the exception to the caller
    (the interface layer / CLI loop), causing a crash-free session violation.
    Additionally, handler exceptions exposed raw exception class names in the
    response message (e.g. "Request processing failed: ValueError: ...").

Fix (interfaces/manager.py, process_request() method):
    - The no-handler check was moved outside the try/except block and now
      returns a graceful Response(status="error") instead of raising.
    - The handler exception catch now returns a sanitized message that does not
      include the raw exception class name or traceback.

This file must never be deleted (regression protection).
"""

from __future__ import annotations

import threading
import unittest
from datetime import datetime, timezone
from typing import Optional
import uuid

from interfaces.base import Interface, Request, Response
from interfaces.manager import InterfaceManager


class MockInterface(Interface):
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


def _req() -> Request:
    return Request(
        request_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        user_input="test input",
        interface_type="cli",
        user_id="user-reg-48",
    )


class TestIssue48ProcessRequestNoCrash(unittest.TestCase):
    """
    Issue #48: process_request() must never raise — always return Response.
    """

    def _make_manager(self) -> tuple[InterfaceManager, MockInterface]:
        manager = InterfaceManager()
        iface = MockInterface("cli")
        manager.register_interface(iface)
        manager.start_interface("cli")
        return manager, iface

    def test_no_handler_returns_error_response_not_exception(self) -> None:
        """
        REGRESSION: process_request() with no handler must return
        Response(status='error'), never raise InterfaceManagerError.
        """
        manager, iface = self._make_manager()
        iface.received_requests.append(_req())
        raw = manager.receive("cli")
        # This must NOT raise
        resp = manager.process_request(raw)
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.status, "error")

    def test_no_handler_response_has_human_message(self) -> None:
        """
        Error response when no handler set must have a human-readable message.
        """
        manager, iface = self._make_manager()
        iface.received_requests.append(_req())
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertIsInstance(resp.message, str)
        self.assertGreater(len(resp.message), 0)
        # Must not expose raw system token
        raw_tokens = {"HANDLER NOT SET", "REQUEST HANDLER NOT SET", "INTERFACEMANAGERERROR"}
        self.assertNotIn(resp.message.strip().upper(), raw_tokens)

    def test_handler_exception_returns_error_response(self) -> None:
        """
        REGRESSION: Handler raising an exception must produce Response(status='error'),
        not propagate the exception.
        """
        manager, iface = self._make_manager()

        def crashing_handler(request: Request) -> Response:
            raise RuntimeError("Internal parsing error: malformed AST node at offset 42")

        manager.set_request_handler(crashing_handler)
        iface.received_requests.append(_req())
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.status, "error")

    def test_handler_exception_message_hides_class_name(self) -> None:
        """
        REGRESSION: Error message must NOT expose exception class names to user.
        """
        manager, iface = self._make_manager()

        def bad_handler(request: Request) -> Response:
            raise ValueError("internal state inconsistency")

        manager.set_request_handler(bad_handler)
        iface.received_requests.append(_req())
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertNotIn("ValueError", resp.message)
        self.assertNotIn("RuntimeError", resp.message)
        self.assertNotIn("Traceback", resp.message)

    def test_error_response_echoes_request_id(self) -> None:
        """Error response must always echo the original request_id."""
        manager, iface = self._make_manager()
        req = _req()
        iface.received_requests.append(req)
        raw = manager.receive("cli")
        resp = manager.process_request(raw)
        self.assertEqual(resp.request_id, req.request_id)

    def test_multiple_no_handler_calls_all_return_responses(self) -> None:
        """Multiple calls without a handler all return graceful error responses."""
        manager, iface = self._make_manager()
        for _ in range(5):
            req = _req()
            iface.received_requests.append(req)
            raw = manager.receive("cli")
            resp = manager.process_request(raw)
            self.assertEqual(resp.status, "error")
            self.assertIsInstance(resp.message, str)

    def test_concurrent_no_handler_calls_thread_safe(self) -> None:
        """Concurrent process_request() without handler is thread-safe."""
        manager, iface = self._make_manager()
        errors: list[Exception] = []
        responses: list[Response] = []

        def call_process() -> None:
            try:
                req = _req()
                iface.received_requests.append(req)
                raw = manager.receive("cli")
                if raw:
                    resp = manager.process_request(raw)
                    responses.append(resp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_process) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Unexpected exceptions: {errors}")
        # All returned responses must be Response objects
        for r in responses:
            self.assertIsInstance(r, Response)


if __name__ == "__main__":
    unittest.main()

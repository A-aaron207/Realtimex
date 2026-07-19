"""
Unit tests for Realtimex Interface Layer.

Tests cover:
- Interface contract implementation
- Request/Response objects
- SessionManager thread-safety
- InterfaceRegistry operations
- InterfaceManager request routing
- Authentication/Authorization
- Serialization
"""

from __future__ import annotations

import json
import pytest
import threading
from datetime import datetime, timezone
from typing import Optional

from interfaces.base import Interface, Request, Response
from interfaces.manager import InterfaceManager
from interfaces.session import SessionManager
from interfaces.registry import InterfaceRegistry
from interfaces.authentication import AuthenticationManager, AuthorizationManager
from interfaces.serialization import SerializationManager
from interfaces.cli import CLIInterface
from interfaces.api import RESTInterface
from interfaces.api.websocket import WebSocketInterface
from interfaces.voice import VoiceInterface
from interfaces.gui import GUIInterface
from interfaces.exceptions import (
    InterfaceInitializationError,
    SessionError,
    AuthenticationError,
    SerializationError,
)


# Test fixtures

class MockInterface(Interface):
    """Mock interface for testing."""
    
    def __init__(self, name: str = "mock"):
        super().__init__(name=name, interface_type="mock")
        self.received_requests = []
        self.sent_responses = []
    
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


# Test Interface contract

class TestInterfaceContract:
    """Test Interface ABC implementation."""
    
    def test_interface_cannot_be_instantiated(self):
        """Interface ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Interface(name="test", interface_type="test")
    
    def test_mock_interface_implements_contract(self):
        """Mock interface implements all required methods."""
        interface = MockInterface()
        assert hasattr(interface, 'initialize')
        assert hasattr(interface, 'start')
        assert hasattr(interface, 'stop')
        assert hasattr(interface, 'shutdown')
        assert hasattr(interface, 'receive')
        assert hasattr(interface, 'send')
    
    def test_concrete_interfaces_are_callable(self):
        """All concrete interfaces can be instantiated."""
        interfaces = [
            CLIInterface(),
            RESTInterface(),
            WebSocketInterface(),
            VoiceInterface(),
            GUIInterface(),
        ]
        for interface in interfaces:
            assert interface is not None


# Test Request/Response objects

class TestRequestResponse:
    """Test Request and Response dataclasses."""
    
    def test_request_creation(self):
        """Request objects can be created with proper fields."""
        now = datetime.now(timezone.utc)
        request = Request(
            request_id="req-1",
            session_id="sess-1",
            timestamp=now,
            user_input="test input",
            interface_type="cli",
            user_id="user-1",
            metadata={"key": "value"},
        )
        assert request.request_id == "req-1"
        assert request.session_id == "sess-1"
        assert request.user_input == "test input"
        assert request.interface_type == "cli"
    
    def test_response_creation(self):
        """Response objects can be created with proper fields."""
        response = Response(
            request_id="req-1",
            status="success",
            message="Test message",
            artifacts={"data": "artifact"},
            events=["event1", "event2"],
        )
        assert response.request_id == "req-1"
        assert response.status == "success"
        assert response.message == "Test message"
        assert len(response.events) == 2
    
    def test_response_to_dict(self):
        """Response can be converted to dict."""
        response = Response(
            request_id="req-1",
            status="success",
            message="Test",
        )
        data = response.to_dict()
        assert data["request_id"] == "req-1"
        assert data["status"] == "success"


# Test SessionManager

class TestSessionManager:
    """Test SessionManager functionality."""
    
    def test_create_session(self):
        """Sessions can be created."""
        manager = SessionManager()
        session_id = manager.create_session(
            user_id="user-1",
            interface_type="cli",
        )
        assert session_id is not None
    
    def test_get_session(self):
        """Sessions can be retrieved."""
        manager = SessionManager()
        session = manager.create_session(
            user_id="user-1",
            interface_type="cli",
        )
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.user_id == "user-1"
        assert retrieved.interface_type == "cli"
    
    def test_add_task_to_session(self):
        """Tasks can be added to sessions."""
        manager = SessionManager()
        session = manager.create_session(
            user_id="user-1",
            interface_type="cli",
        )
        manager.add_task(session.session_id, "task-1")
        
        retrieved = manager.get_session(session.session_id)
        assert "task-1" in retrieved.active_tasks
    
    def test_remove_task_from_session(self):
        """Tasks can be removed from sessions."""
        manager = SessionManager()
        session = manager.create_session(
            user_id="user-1",
            interface_type="cli",
        )
        manager.add_task(session.session_id, "task-1")
        manager.remove_task(session.session_id, "task-1")
        
        retrieved = manager.get_session(session.session_id)
        assert "task-1" not in retrieved.active_tasks
    
    def test_close_session(self):
        """Sessions can be closed."""
        manager = SessionManager()
        session = manager.create_session(
            user_id="user-1",
            interface_type="cli",
        )
        manager.close_session(session.session_id)
        
        retrieved = manager.get_session(session.session_id)
        assert retrieved is None
    
    def test_session_manager_thread_safety(self):
        """SessionManager operations are thread-safe."""
        manager = SessionManager()
        sessions = []
        errors = []
        
        def create_sessions(count: int) -> None:
            try:
                for i in range(count):
                    session = manager.create_session(
                        user_id=f"user-{i}",
                        interface_type="cli",
                    )
                    sessions.append(session.session_id)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=create_sessions, args=(10,))
            for _ in range(5)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0
        assert len(sessions) == 50


# Test InterfaceRegistry

class TestInterfaceRegistry:
    """Test InterfaceRegistry functionality."""
    
    def test_register_interface(self):
        """Interfaces can be registered."""
        registry = InterfaceRegistry()
        interface = MockInterface()
        
        registry.register(interface)
        retrieved = registry.get("mock")
        assert retrieved is interface
    
    def test_unregister_interface(self):
        """Interfaces can be unregistered."""
        registry = InterfaceRegistry()
        interface = MockInterface()
        
        registry.register(interface)
        registry.unregister("mock")
        retrieved = registry.get("mock")
        assert retrieved is None
    
    def test_list_interfaces(self):
        """All interfaces can be listed."""
        registry = InterfaceRegistry()
        interface1 = MockInterface("mock1")
        interface2 = MockInterface("mock2")
        interface1.interface_type = "mock1"
        interface2.interface_type = "mock2"
        
        registry.register(interface1)
        registry.register(interface2)
        
        interfaces = registry.list()
        assert len(interfaces) == 2


# Test InterfaceManager

class TestInterfaceManager:
    """Test InterfaceManager functionality."""
    
    def test_interface_manager_creation(self):
        """InterfaceManager can be created."""
        manager = InterfaceManager()
        assert manager is not None
    
    def test_register_interface_with_manager(self):
        """Interfaces can be registered with manager."""
        manager = InterfaceManager()
        interface = MockInterface()
        
        manager.register_interface(interface)
        retrieved = manager.registry.get("mock")
        assert retrieved is interface
    
    def test_set_request_handler(self):
        """Request handler can be set."""
        manager = InterfaceManager()
        
        def handler(request: Request) -> Response:
            return Response(
                request_id=request.request_id,
                status="success",
                message="Handled",
            )
        
        manager.set_request_handler(handler)
        assert manager._request_handler is not None


# Test AuthenticationManager

class TestAuthenticationManager:
    """Test AuthenticationManager functionality."""
    
    def test_generate_token(self):
        """Tokens can be generated."""
        manager = AuthenticationManager()
        token = manager.generate_token("user-1")
        assert token is not None
        assert len(token) > 0
    
    def test_validate_token(self):
        """Tokens can be validated."""
        manager = AuthenticationManager()
        token = manager.generate_token("user-1")
        
        user_id = manager.validate_token(token)
        assert user_id == "user-1"
    
    def test_invalid_token_returns_none(self):
        """Invalid tokens return None."""
        manager = AuthenticationManager()
        user_id = manager.validate_token("invalid-token")
        assert user_id is None
    
    def test_refresh_token(self):
        """Tokens can be refreshed."""
        manager = AuthenticationManager()
        token = manager.generate_token("user-1")
        
        new_token = manager.refresh_token(token)
        assert new_token is not None
        assert new_token != token
        
        user_id = manager.validate_token(new_token)
        assert user_id == "user-1"
    
    def test_revoke_token(self):
        """Tokens can be revoked."""
        manager = AuthenticationManager()
        token = manager.generate_token("user-1")
        
        manager.revoke_token(token)
        user_id = manager.validate_token(token)
        assert user_id is None


# Test AuthorizationManager

class TestAuthorizationManager:
    """Test AuthorizationManager functionality."""
    
    def test_assign_role(self):
        """Roles can be assigned."""
        manager = AuthorizationManager()
        result = manager.assign_role("user-1", "admin")
        assert result is True
    
    def test_check_permission(self):
        """Permissions can be checked."""
        manager = AuthorizationManager()
        manager.assign_role("user-1", "admin")
        
        has_permission = manager.check_permission("user-1", "task.create")
        assert has_permission is True
    
    def test_user_without_permission(self):
        """Users without permission return False."""
        manager = AuthorizationManager()
        manager.assign_role("user-1", "viewer")
        
        has_permission = manager.check_permission("user-1", "task.delete")
        assert has_permission is False
    
    def test_get_user_permissions(self):
        """User permissions can be retrieved."""
        manager = AuthorizationManager()
        manager.assign_role("user-1", "user")
        
        permissions = manager.get_user_permissions("user-1")
        assert "task.create" in permissions
        assert "task.read" in permissions
    
    def test_create_custom_role(self):
        """Custom roles can be created."""
        manager = AuthorizationManager()
        result = manager.create_role("custom", {"custom.perm"})
        assert result is True
        
        manager.assign_role("user-1", "custom")
        has_permission = manager.check_permission("user-1", "custom.perm")
        assert has_permission is True


# Test SerializationManager

class TestSerializationManager:
    """Test SerializationManager functionality."""
    
    def test_serialize_request(self):
        """Requests can be serialized."""
        manager = SerializationManager()
        now = datetime.now(timezone.utc)
        request = Request(
            request_id="req-1",
            session_id="sess-1",
            timestamp=now,
            user_input="test",
            interface_type="cli",
            user_id="user-1",
        )
        
        serialized = manager.serialize_request(request)
        assert isinstance(serialized, str)
        data = json.loads(serialized)
        assert data["request_id"] == "req-1"
    
    def test_deserialize_request(self):
        """Requests can be deserialized."""
        manager = SerializationManager()
        now = datetime.now(timezone.utc)
        request = Request(
            request_id="req-1",
            session_id="sess-1",
            timestamp=now,
            user_input="test",
            interface_type="cli",
            user_id="user-1",
        )
        
        serialized = manager.serialize_request(request)
        deserialized = manager.deserialize_request(serialized)
        
        assert deserialized.request_id == "req-1"
        assert deserialized.session_id == "sess-1"
    
    def test_serialize_response(self):
        """Responses can be serialized."""
        manager = SerializationManager()
        response = Response(
            request_id="req-1",
            status="success",
            message="Test message",
        )
        
        serialized = manager.serialize_response(response)
        assert isinstance(serialized, str)
        data = json.loads(serialized)
        assert data["request_id"] == "req-1"
    
    def test_deserialize_response(self):
        """Responses can be deserialized."""
        manager = SerializationManager()
        response = Response(
            request_id="req-1",
            status="success",
            message="Test",
        )
        
        serialized = manager.serialize_response(response)
        deserialized = manager.deserialize_response(serialized)
        
        assert deserialized.request_id == "req-1"
        assert deserialized.status == "success"


# Test concrete interfaces

class TestConcreteInterfaces:
    """Test concrete interface implementations."""
    
    def test_cli_interface_initialization(self):
        """CLI interface can be initialized."""
        interface = CLIInterface()
        interface.initialize()
        assert interface.name == "CLI"
    
    def test_rest_interface_initialization(self):
        """REST interface can be initialized."""
        interface = RESTInterface()
        interface.initialize()
        assert interface.name == "REST API"
    
    def test_websocket_interface_initialization(self):
        """WebSocket interface can be initialized."""
        interface = WebSocketInterface()
        interface.initialize()
        assert interface.name == "WebSocket"
    
    def test_voice_interface_initialization(self):
        """Voice interface can be initialized."""
        interface = VoiceInterface()
        interface.initialize()
        assert interface.name == "Voice"
    
    def test_gui_interface_initialization(self):
        """GUI interface can be initialized."""
        interface = GUIInterface()
        interface.initialize()
        assert interface.name == "GUI"

    def test_manager_public_api(self):
        """Test public API methods of InterfaceManager."""
        manager = InterfaceManager()
        interface = MockInterface()
        
        # Test register
        manager.register(interface)
        assert len(manager.interfaces()) == 1
        assert manager.interfaces()[0] is interface
        
        # Test start/stop
        manager.start()
        assert interface.is_running is True
        
        # Check sessions
        assert len(manager.sessions()) == 0
        
        manager.stop()
        assert interface.is_running is False

    def test_cli_parser(self):
        """Test CLIParser functionality."""
        from interfaces.cli.parser import CLIParser
        
        # Simple command
        parsed = CLIParser.parse_command("task status 123")
        assert parsed["action"] == "task"
        assert parsed["args"] == ["status", "123"]
        
        # Quoted strings
        parsed = CLIParser.parse_command('task create "My complex goal" --priority high')
        assert parsed["action"] == "task"
        assert parsed["args"] == ["create", "My complex goal"]
        assert parsed["options"] == {"priority": "high"}

    def test_rest_interface_endpoints(self):
        """Test REST interface local endpoints (health, metrics)."""
        interface = RESTInterface(port=8990)
        interface.initialize()
        interface.start()
        
        import urllib.request
        import json
        
        try:
            # Test health
            with urllib.request.urlopen("http://localhost:8990/health") as response:
                assert response.status == 200
                data = json.loads(response.read().decode('utf-8'))
                assert data["status"] == "healthy"
                
            # Test metrics
            with urllib.request.urlopen("http://localhost:8990/metrics") as response:
                assert response.status == 200
                data = json.loads(response.read().decode('utf-8'))
                assert data["total_requests"] >= 1
        finally:
            interface.stop()

    def test_websocket_interface_connections(self):
        """Test WebSocket client connection registering and broadcasting."""
        interface = WebSocketInterface(port=8991)
        interface.initialize()
        interface.start()
        
        try:
            assert interface.connection_count() == 0
            
            # Connect mock client
            interface.connect("client-123")
            assert interface.connection_count() == 1
            
            # Disconnect client
            interface.disconnect("client-123")
            assert interface.connection_count() == 0
        finally:
            interface.stop()

    def test_rest_integration_request_response_flow(self):
        """Test full HTTP request -> InterfaceManager -> Request Handler -> Response -> HTTP Client flow."""
        manager = InterfaceManager()
        interface = RESTInterface(port=8995)
        manager.register(interface)
        
        # Simple request handler that echoes/handles the action
        def sample_handler(request: Request) -> Response:
            action = request.user_input.get("action")
            if action == "task.create":
                return Response(
                    request_id=request.request_id,
                    status="success",
                    message="Task successfully booted!",
                    data={"task_id": "test-task-123", "state": "running"},
                    metadata={"session_id": request.session_id}
                )
            return Response(request_id=request.request_id, status="error", message="Unknown action")
            
        manager.set_request_handler(sample_handler)
        
        # Start manager & REST interface
        manager.start()
        
        import urllib.request
        import json
        import time
        
        # We need a background thread to poll the interface manager since the REST handler
        # puts the request in the queue and blocks, waiting for the response.
        # The background thread will simulate the kernel polling loop.
        stop_event = threading.Event()
        
        def mock_kernel_loop():
            while not stop_event.is_set():
                req = manager.receive()
                if req:
                    # process and send back
                    res = manager.process_request(req)
                    manager.send(res)
                time.sleep(0.05)
                
        kernel_thread = threading.Thread(target=mock_kernel_loop, daemon=True)
        kernel_thread.start()
        
        try:
            # Make HTTP POST request to submit a task
            url = "http://localhost:8995/tasks"
            post_data = json.dumps({
                "goal": "Write a compiler",
                "priority": "high",
                "metadata": {"test": True}
            }).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=post_data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                assert response.status == 201
                resp_data = json.loads(response.read().decode('utf-8'))
                assert resp_data["status"] == "success"
                assert resp_data["message"] == "Task successfully booted!"
                assert resp_data["data"]["task_id"] == "test-task-123"
        finally:
            stop_event.set()
            kernel_thread.join(timeout=1.0)
            manager.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


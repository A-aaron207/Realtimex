# Realtimex Interface Layer

The Interface Layer provides all external communication with the Realtimex Kernel. It acts as a unified translation layer between multiple interface technologies and the core kernel, ensuring the kernel remains completely independent of any specific interface implementation.

## Philosophy

- **Interfaces translate, Kernel executes**: The Interface Layer translates between external communication protocols and kernel requests. No business logic resides in interfaces.
- **Interface independence**: The Kernel is completely independent of any specific interface technology.
- **Uniform behavior**: Every interface behaves identically from the kernel's perspective.
- **Extensibility**: New interfaces can be added without modifying the kernel.

## Architecture

### Core Components

```
External Clients
        │
        ├─→ CLI
        ├─→ REST API
        ├─→ WebSocket
        ├─→ Voice (placeholder)
        └─→ GUI (placeholder)
        │
        ▼
Interface Manager
        │
        ├─→ Registry (interface discovery)
        ├─→ Session Manager (session tracking)
        ├─→ Authentication Manager (token/auth)
        ├─→ Authorization Manager (permissions)
        └─→ Serialization Manager (JSON/objects)
        │
        ▼
    Kernel
```

### Design Patterns

1. **Interface Contract**: All interfaces inherit from abstract `Interface` base class
2. **Request/Response**: Standardized dataclasses for all external communication
3. **Session Management**: Separate session tracking across all interfaces
4. **Thread-safe**: RLock protection on all managers
5. **Event-driven**: All interface operations emit events to EventBus

## Folder Structure

```
interfaces/
│
├── __init__.py                 # Module exports
├── base.py                     # Interface ABC, Request/Response
├── manager.py                  # Central orchestrator
├── registry.py                 # Interface registry
├── session.py                  # Session management
├── authentication.py           # Auth/Authz
├── serialization.py            # JSON serialization
├── exceptions.py               # Custom exceptions
│
├── cli/
│   ├── __init__.py
│   ├── interface.py            # CLI interface
│   └── parser.py               # Command parser
│
├── api/
│   ├── __init__.py
│   ├── rest.py                 # REST API interface
│   ├── websocket.py            # WebSocket interface
│   └── models.py               # REST models
│
├── gui/
│   ├── __init__.py
│   └── interface.py            # GUI placeholder
│
└── voice/
    ├── __init__.py
    └── interface.py            # Voice placeholder
```

## Public API

### Interface Manager

```python
manager = InterfaceManager(event_bus=event_bus)

# Register interfaces
manager.register_interface(cli_interface)
manager.register_interface(rest_interface)

# Set kernel request handler
manager.set_request_handler(kernel.handle_request)

# Start all interfaces
manager.start_all()

# Process requests from interfaces
requests = manager.get_pending_requests()
for request in requests:
    response = kernel.handle_request(request)
    manager.send_response(response)

# Stop all interfaces
manager.stop_all()
```

### Interface Implementation

```python
# Implement custom interface
class CustomInterface(Interface):
    def initialize(self) -> None:
        # Setup
        pass
    
    def start(self) -> None:
        self.is_running = True
    
    def stop(self) -> None:
        self.is_running = False
    
    def shutdown(self) -> None:
        self.stop()
    
    def receive(self) -> Optional[Request]:
        # Get request from external source
        return request
    
    def send(self, response: Response) -> None:
        # Send response to external client
        pass
```

### Session Management

```python
manager = SessionManager()

# Create session
session = manager.create_session(
    user_id="user-1",
    interface_type="rest",
    context={"api_version": "v1"}
)

# Track tasks
manager.add_task(session.session_id, "task-1")

# Update context
manager.update_context(session.session_id, {"step": "processing"})

# Close session
manager.close_session(session.session_id)
```

### Authentication

```python
auth = AuthenticationManager(token_ttl_hours=24)

# Generate token
token = auth.generate_token("user-1")

# Validate token
user_id = auth.validate_token(token)

# Refresh token
new_token = auth.refresh_token(token)

# Revoke token
auth.revoke_token(token)

# Cleanup expired tokens
removed = auth.cleanup_expired_tokens()
```

### Authorization

```python
authz = AuthorizationManager()

# Assign role
authz.assign_role("user-1", "admin")

# Check permission
has_perm = authz.check_permission("user-1", "task.create")

# Get user permissions
perms = authz.get_user_permissions("user-1")

# Create custom role
authz.create_role("reviewer", {"task.read", "workflow.read"})
```

### Serialization

```python
serializer = SerializationManager()

# Serialize Request
json_str = serializer.serialize_request(request)

# Deserialize Request
request = serializer.deserialize_request(json_str)

# Serialize Response
json_str = serializer.serialize_response(response)

# Deserialize Response
response = serializer.deserialize_response(json_str)
```

## Request/Response Flow

```
1. External Client sends request to Interface
2. Interface.receive() creates Request object
3. InterfaceManager.process_request() routes to Kernel
4. Kernel handles Request
5. Kernel returns Response
6. InterfaceManager.send_response() sends to Interface
7. Interface.send() delivers Response to Client
```

## Request Object

```python
Request(
    request_id="req-uuid",           # Unique request ID
    session_id="sess-uuid",          # Session ID
    timestamp=datetime.now(),        # Request timestamp
    user_input="command",            # Input from user
    interface_type="cli",            # Which interface
    user_id="user-1",               # Which user
    metadata={"key": "value"}        # Additional data
)
```

## Response Object

```python
Response(
    request_id="req-uuid",           # Links to request
    status="success",                # success, error, pending
    message="Result message",        # Human-readable message
    artifacts={"data": ...},         # Result data
    events=["event1", "event2"],    # Related events
    metadata={"key": "value"}        # Additional data
)
```

## Interfaces

### CLI Interface

- Interactive and single-command modes
- Command parsing and completion
- Colored output support
- Progress indicators
- Streaming responses

### REST API

- Task submission (`POST /tasks`)
- Task status (`GET /tasks/{id}`)
- Task cancellation (`DELETE /tasks/{id}`)
- Memory queries (`GET /memory`)
- Health endpoint (`GET /health`)
- Metrics endpoint (`GET /metrics`)

### WebSocket API

- Real-time task updates
- Streaming model responses
- Event notifications
- Progress updates
- Bidirectional communication

### Voice Interface (Placeholder)

Ready for future implementation with:
- Speech-to-text input
- Voice command parsing
- Text-to-speech output
- Natural language interaction

### GUI Interface (Placeholder)

Ready for future implementation with:
- Task dashboard
- Workflow visualization
- Real-time monitoring
- Interactive controls
- Resource usage graphs

## Events

The Interface Layer emits the following events:

- `InterfaceEventType.INTERFACE_REGISTERED` - Interface registered
- `InterfaceEventType.INTERFACE_STARTED` - Interface started
- `InterfaceEventType.INTERFACE_STOPPED` - Interface stopped
- `InterfaceEventType.REQUEST_RECEIVED` - Request received
- `InterfaceEventType.RESPONSE_SENT` - Response sent
- `InterfaceEventType.SESSION_CREATED` - Session created
- `InterfaceEventType.SESSION_CLOSED` - Session closed
- `InterfaceEventType.CLIENT_CONNECTED` - Client connected (WebSocket)
- `InterfaceEventType.CLIENT_DISCONNECTED` - Client disconnected

## Thread Safety

All managers use `RLock` (reentrant locks) to ensure thread-safe operations:
- Multiple threads can safely create sessions
- Multiple threads can safely register interfaces
- Multiple threads can safely emit events
- Same thread can acquire lock multiple times

## Error Handling

Custom exceptions for proper error handling:

- `InterfaceError` - Base exception
- `InterfaceInitializationError` - Initialization failed
- `InterfaceNotAvailableError` - Interface not running
- `RequestValidationError` - Request validation failed
- `ResponseSerializationError` - Serialization failed
- `SessionError` - Session management error
- `AuthenticationError` - Authentication failed
- `AuthorizationError` - Authorization failed
- `InterfaceManagerError` - Manager operation failed
- `SerializationError` - Serialization/deserialization failed

## Integration with Kernel

The Interface Layer integrates with the Kernel through:

1. **Request Handler Callback**: Kernel registers callback for processing requests
2. **Event Bus**: Interface Layer emits events for interface operations
3. **Session Manager**: Tracks user sessions across interfaces
4. **Authentication**: Validates user credentials and tokens

Example integration:

```python
# In Kernel initialization
interface_manager = InterfaceManager(event_bus=event_bus)

# Register interfaces
interface_manager.register_interface(CLIInterface())
interface_manager.register_interface(RESTInterface(port=8000))
interface_manager.register_interface(WebSocketInterface(port=8001))

# Set kernel request handler
interface_manager.set_request_handler(kernel.handle_request)

# Start all interfaces
interface_manager.start_all()

# In kernel request loop
while kernel.is_running:
    request = interface_manager.receive()
    if request:
        response = kernel.handle_request(request)
        interface_manager.send_response(response)
```

## Session Management

Sessions track user activity across interfaces:

```python
Session {
    session_id: str              # Unique session ID
    user_id: str                 # User owning session
    interface_type: str          # CLI, REST, WebSocket, etc.
    created_at: datetime         # Session creation time
    last_activity: datetime      # Last activity timestamp
    active_tasks: list[str]      # Task IDs active in session
    context: dict                # Session context data
    metadata: dict               # Additional metadata
    
    # Properties
    age_seconds: float           # Time since creation
    idle_seconds: float          # Time since last activity
}
```

## Design Rules

✓ Thread-safe everywhere
✓ Event-driven architecture
✓ Storage-independent
✓ Extensible interface system
✓ No business logic in interfaces
✓ No AI logic in interfaces
✓ No scheduling logic in interfaces
✓ No execution logic in interfaces
✓ Kernel completely independent of interface technology

## Extensibility

Adding a new interface is simple:

1. Create new class inheriting from `Interface`
2. Implement the required methods (initialize, start, stop, shutdown, receive, send)
3. Register with InterfaceManager
4. Interface receives requests and sends responses

Example:

```python
class MyInterface(Interface):
    def __init__(self):
        super().__init__(name="MyInterface", interface_type="mytype")
    
    def initialize(self) -> None:
        pass
    
    def start(self) -> None:
        self.is_running = True
    
    def stop(self) -> None:
        self.is_running = False
    
    def shutdown(self) -> None:
        self.stop()
    
    def receive(self) -> Optional[Request]:
        # Get request from external source
        return Request(...)
    
    def send(self, response: Response) -> None:
        # Send response to external client
        pass

# Use the interface
interface = MyInterface()
interface_manager.register_interface(interface)
interface_manager.start_interface("mytype")
```

## Testing

The Interface Layer includes comprehensive tests:

- Interface contract implementation
- Request/Response object creation
- SessionManager thread-safety
- InterfaceRegistry operations
- InterfaceManager request routing
- Authentication/Authorization
- Serialization/Deserialization
- All concrete interface implementations

Run tests with:

```bash
python3 -m pytest specs/test_interfaces.py -v
```

## Production Readiness

The Interface Layer is production-grade with:

✓ Complete thread-safety
✓ Comprehensive error handling
✓ Extensive logging
✓ Event emission for all operations
✓ Session tracking and cleanup
✓ Token authentication
✓ Role-based authorization
✓ JSON serialization
✓ Multiple concurrent interfaces
✓ Extensible design
✓ Full test coverage
✓ Comprehensive documentation

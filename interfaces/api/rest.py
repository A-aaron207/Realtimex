"""
REST API Interface for Realtimex.

Provides RESTful HTTP API for programmatic access.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from interfaces.base import Interface, Request, Response
from interfaces.exceptions import InterfaceInitializationError
from interfaces.api.models import (
    TaskCreateRequest,
    TaskResponse,
    MemoryQueryRequest,
    HealthResponse,
    MetricsResponse,
)


class RESTRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for REST API."""
    
    # Share interface reference through class variable
    rest_interface: Optional[RESTInterface] = None
    
    def _send_json(self, status_code: int, data: Any) -> None:
        """Helper to send JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

    def do_POST(self) -> None:
        """Handle POST requests."""
        if not self.rest_interface:
            self._send_json(500, {"error": "REST Interface not available"})
            return

        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/tasks':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                
                # Parse JSON request
                data = json.loads(body) if body else {}
                
                goal = data.get('goal')
                if not goal:
                    self.rest_interface.increment_failed()
                    self._send_json(400, {"error": "Missing required field: goal"})
                    return
                
                # Create Request object
                request = Request(
                    request_id=str(uuid.uuid4()),
                    session_id=data.get('session_id', str(uuid.uuid4())),
                    timestamp=datetime.now(timezone.utc),
                    user_input={
                        "action": "task.create",
                        "goal": goal,
                        "priority": data.get('priority', 'normal'),
                        "metadata": data.get('metadata', {}),
                    },
                    interface_type='rest',
                    user_id=data.get('user_id', 'rest_user'),
                    metadata=data.get('metadata', {}),
                )
                
                self.rest_interface.increment_requests()
                event = self.rest_interface.queue_request(request)
                
                # Wait for response (5.0s timeout)
                response = self.rest_interface.get_response(request.request_id, timeout=5.0)
                
                if response:
                    if response.status == "success":
                        self.rest_interface.increment_successful()
                        self._send_json(201, response.to_dict())
                    else:
                        self.rest_interface.increment_failed()
                        self._send_json(400, response.to_dict())
                else:
                    # Timeout fallback - return 202 Accepted with Request ID
                    self.rest_interface.increment_successful()
                    self._send_json(202, {
                        "request_id": request.request_id,
                        "status": "accepted",
                        "message": "Task creation request accepted, processing asynchronously."
                    })
                
            except Exception as e:
                self.rest_interface.increment_failed()
                self._send_json(400, {"error": f"Invalid request body: {e}"})
        else:
            self._send_json(404, {"error": "Not found"})
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        if not self.rest_interface:
            self._send_json(500, {"error": "REST Interface not available"})
            return

        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        if path == '/health':
            self.rest_interface.increment_requests()
            self.rest_interface.increment_successful()
            self._send_json(200, {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0"
            })
            return
            
        elif path == '/metrics':
            self.rest_interface.increment_requests()
            self.rest_interface.increment_successful()
            self._send_json(200, self.rest_interface.get_metrics())
            return

        elif path == '/memory':
            query = query_params.get('query', [''])[0]
            scope = query_params.get('scope', [None])[0]
            
            request = Request(
                request_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                user_input={
                    "action": "memory.search",
                    "query": query,
                    "scope": scope
                },
                interface_type='rest',
                user_id='rest_user'
            )
            
            self.rest_interface.increment_requests()
            event = self.rest_interface.queue_request(request)
            response = self.rest_interface.get_response(request.request_id, timeout=5.0)
            
            if response:
                if response.status == "success":
                    self.rest_interface.increment_successful()
                    self._send_json(200, response.to_dict())
                else:
                    self.rest_interface.increment_failed()
                    self._send_json(400, response.to_dict())
            else:
                self.rest_interface.increment_failed()
                self._send_json(504, {"error": "Gateway timeout waiting for memory retrieval."})
            return

        # Check if GET /tasks/{id}
        parts = path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'tasks':
            task_id = parts[1]
            request = Request(
                request_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                user_input={
                    "action": "task.get",
                    "task_id": task_id
                },
                interface_type='rest',
                user_id='rest_user'
            )
            
            self.rest_interface.increment_requests()
            event = self.rest_interface.queue_request(request)
            response = self.rest_interface.get_response(request.request_id, timeout=5.0)
            
            if response:
                if response.status == "success":
                    self.rest_interface.increment_successful()
                    self._send_json(200, response.to_dict())
                else:
                    self.rest_interface.increment_failed()
                    self._send_json(404, {"error": response.message or f"Task {task_id} not found"})
            else:
                self.rest_interface.increment_failed()
                self._send_json(504, {"error": f"Gateway timeout waiting for status of task {task_id}."})
            return
            
        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        if not self.rest_interface:
            self._send_json(500, {"error": "REST Interface not available"})
            return

        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # Check if DELETE /tasks/{id}
        parts = path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'tasks':
            task_id = parts[1]
            request = Request(
                request_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                user_input={
                    "action": "task.cancel",
                    "task_id": task_id
                },
                interface_type='rest',
                user_id='rest_user'
            )
            
            self.rest_interface.increment_requests()
            event = self.rest_interface.queue_request(request)
            response = self.rest_interface.get_response(request.request_id, timeout=5.0)
            
            if response:
                if response.status == "success":
                    self.rest_interface.increment_successful()
                    self._send_json(200, response.to_dict())
                else:
                    self.rest_interface.increment_failed()
                    self._send_json(400, response.to_dict())
            else:
                self.rest_interface.increment_failed()
                self._send_json(504, {"error": f"Gateway timeout waiting for cancellation of task {task_id}."})
            return

        self._send_json(404, {"error": "Not found"})
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass


class RESTInterface(Interface):
    """
    RESTful HTTP API interface for Realtimex.
    
    Supports:
    - Task submission via POST /tasks
    - Task status queries via GET /tasks/{id}
    - Task cancellation via DELETE /tasks/{id}
    - Memory queries via GET /memory
    - Health endpoint via GET /health
    - Metrics endpoint via GET /metrics
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize REST Interface.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            logger: Optional logger instance
        """
        super().__init__(name="REST API", interface_type="rest")
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger("realtimex.interfaces.rest")
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self._pending_requests: list[Request] = []
        self._response_events: dict[str, threading.Event] = {}
        self._pending_responses: dict[str, Response] = {}
        self._lock = threading.RLock()
        
        # Metrics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._start_time = datetime.now(timezone.utc)

    def initialize(self) -> None:
        """Initialize REST interface."""
        try:
            self.logger.info("REST API initializing on %s:%d", self.host, self.port)
            # Set reference in handler
            RESTRequestHandler.rest_interface = self
        except Exception as e:
            raise InterfaceInitializationError(f"REST initialization failed: {e}") from e

    def start(self) -> None:
        """Start REST interface."""
        try:
            # Create and start HTTP server
            self.server = HTTPServer((self.host, self.port), RESTRequestHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_running = True
            self.logger.info("REST API started on http://%s:%d", self.host, self.port)
        except Exception as e:
            self.logger.error("Failed to start REST API: %s", e)
            raise

    def stop(self) -> None:
        """Stop REST interface."""
        try:
            if self.server:
                self.server.shutdown()
                self.is_running = False
                self.logger.info("REST API stopped")
        except Exception as e:
            self.logger.error("Error stopping REST API: %s", e)

    def shutdown(self) -> None:
        """Shutdown REST interface."""
        self.stop()

    def receive(self) -> Optional[Request]:
        """
        Receive request from HTTP client queue.
        
        Returns:
            Request object or None if no requests pending
        """
        with self._lock:
            if self._pending_requests:
                return self._pending_requests.pop(0)
        return None

    def send(self, response: Response) -> None:
        """
        Deliver response to the waiting HTTP thread.
        
        Args:
            response: Response object to send
        """
        with self._lock:
            self._pending_responses[response.request_id] = response
            event = self._response_events.get(response.request_id)
            if event:
                event.set()
            self.logger.debug("Response delivered to HTTP request event: %s", response.request_id)

    def queue_request(self, request: Request) -> threading.Event:
        """Queue request and register a wake-up event."""
        with self._lock:
            self._pending_requests.append(request)
            event = threading.Event()
            self._response_events[request.request_id] = event
            return event

    def get_response(self, request_id: str, timeout: float = 5.0) -> Optional[Response]:
        """Wait for and retrieve the response for a given request ID."""
        event = None
        with self._lock:
            event = self._response_events.get(request_id)
            
        if event:
            event.wait(timeout)
            
        with self._lock:
            self._response_events.pop(request_id, None)
            return self._pending_responses.pop(request_id, None)

    # --- Metrics and State Helpers ---

    def increment_requests(self) -> None:
        with self._lock:
            self._total_requests += 1

    def increment_successful(self) -> None:
        with self._lock:
            self._successful_requests += 1

    def increment_failed(self) -> None:
        with self._lock:
            self._failed_requests += 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            active_sessions = 0
            if hasattr(self, 'session_manager') and self.session_manager:
                active_sessions = self.session_manager.session_count()
            
            return {
                "uptime_seconds": uptime,
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "active_sessions": active_sessions,
            }

"""
Interface Manager for Realtimex.

Orchestrates all interfaces and routes requests to the Kernel.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from events.event import Event, EventPriority
from events.event_types import InterfaceEventType
from interfaces.base import Interface, Request, Response
from interfaces.exceptions import InterfaceManagerError, InterfaceNotAvailableError
from interfaces.registry import InterfaceRegistry
from interfaces.session import SessionManager


class InterfaceManager:
    """
    Central orchestrator for all interfaces.
    
    Responsibilities:
    - Register and manage interfaces
    - Route requests to kernel
    - Broadcast responses back to interfaces
    - Manage user sessions
    - Emit interface events
    
    Thread-safe operations.
    """

    def __init__(
        self,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Interface Manager.
        
        Args:
            event_bus: Optional event bus for emitting events
            logger: Optional logger instance
        """
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.interfaces.manager")
        
        # Core components
        self.registry = InterfaceRegistry(logger=self.logger)
        self.session_manager = SessionManager(logger=self.logger)
        
        # Request handler callback (set by kernel)
        self._request_handler: Callable[[Request], Response] | None = None
        
        # Tracking
        self._is_running = False
        self._lock = threading.RLock()
        self._request_interfaces: dict[str, str] = {}
    
    def set_request_handler(self, handler: Callable[[Request], Response]) -> None:
        """
        Set the request handler callback.
        
        The handler receives requests and returns responses.
        This is typically the kernel's request processing function.
        
        Args:
            handler: Callable that processes requests
        """
        with self._lock:
            self._request_handler = handler
            self.logger.info("Request handler registered")
    
    def register_interface(self, interface: Interface) -> None:
        """
        Register an interface.
        
        Args:
            interface: Interface instance to register
            
        Raises:
            InterfaceManagerError: If registration fails
        """
        with self._lock:
            try:
                self.registry.register(interface)
                interface.manager = self
                interface.session_manager = self.session_manager
                self._emit_event(
                    InterfaceEventType.INTERFACE_REGISTERED,
                    {"interface_type": interface.interface_type, "name": interface.name}
                )
            except Exception as e:
                self.logger.error("Failed to register interface: %s", e)
                raise InterfaceManagerError(f"Failed to register interface: {e}") from e
    
    def start_interface(self, interface_type: str) -> None:
        """
        Start an interface.
        
        Args:
            interface_type: Interface type to start
            
        Raises:
            InterfaceNotAvailableError: If interface not found
            InterfaceManagerError: If startup fails
        """
        with self._lock:
            interface = self.registry.get(interface_type)
            if not interface:
                raise InterfaceNotAvailableError(
                    f"Interface type '{interface_type}' not registered"
                )
            
            try:
                interface.initialize()
                interface.start()
                interface.is_running = True
                self.logger.info("Interface started: %s", interface.name)
                self._emit_event(
                    InterfaceEventType.INTERFACE_STARTED,
                    {"interface_type": interface_type, "name": interface.name}
                )
            except Exception as e:
                self.logger.error("Failed to start interface %s: %s", interface_type, e)
                raise InterfaceManagerError(f"Failed to start interface: {e}") from e
    
    def stop_interface(self, interface_type: str) -> None:
        """
        Stop an interface.
        
        Args:
            interface_type: Interface type to stop
            
        Raises:
            InterfaceNotAvailableError: If interface not found
        """
        with self._lock:
            interface = self.registry.get(interface_type)
            if not interface:
                raise InterfaceNotAvailableError(
                    f"Interface type '{interface_type}' not registered"
                )
            
            try:
                interface.stop()
                interface.is_running = False
                self.logger.info("Interface stopped: %s", interface.name)
                self._emit_event(
                    InterfaceEventType.INTERFACE_STOPPED,
                    {"interface_type": interface_type, "name": interface.name}
                )
            except Exception as e:
                self.logger.error("Error stopping interface %s: %s", interface_type, e)
    
    def start_all(self) -> int:
        """
        Start all registered interfaces.
        
        Returns:
            Number of interfaces started
        """
        with self._lock:
            started = 0
            for interface in self.registry.list_all():
                try:
                    self.start_interface(interface.interface_type)
                    started += 1
                except Exception as e:
                    self.logger.warning("Failed to start interface %s: %s", interface.name, e)
            
            self._is_running = True
            self.logger.info("Interface Manager started with %d interfaces", started)
            return started
    
    def stop_all(self) -> int:
        """
        Stop all running interfaces.
        
        Returns:
            Number of interfaces stopped
        """
        with self._lock:
            stopped = 0
            for interface in self.registry.list_all():
                if interface.is_running:
                    try:
                        self.stop_interface(interface.interface_type)
                        stopped += 1
                    except Exception as e:
                        self.logger.warning("Error stopping interface %s: %s", interface.name, e)
            
            self._is_running = False
            self.logger.info("Interface Manager stopped")
            return stopped
    
    def shutdown(self) -> None:
        """Perform shutdown of all interfaces."""
        with self._lock:
            for interface in self.registry.list_all():
                try:
                    interface.shutdown()
                except Exception as e:
                    self.logger.error("Error during shutdown of %s: %s", interface.name, e)
            
            self.logger.info("Interface Manager shutdown complete")
    
    def process_request(self, request: Request) -> Response:
        """
        Process a request.

        Routes request to handler and generates response. Always returns a
        Response — never raises — so the conversation layer stays crash-free.

        Args:
            request: Request object

        Returns:
            Response object (status="error" when handler is missing or fails)
        """
        # Map request to its interface type for response routing (outside lock so
        # we can safely reference it during event emission below)
        with self._lock:
            self._request_interfaces[request.request_id] = request.interface_type
            handler = self._request_handler

        # No handler registered — return a graceful error response instead of raising
        if not handler:
            self.logger.warning(
                "process_request called with no handler set (request_id=%s)",
                request.request_id,
            )
            return Response(
                request_id=request.request_id,
                status="error",
                message="I'm not ready to handle requests yet. Please try again shortly.",
            )

        try:
            # Update session activity
            if request.session_id:
                session = self.session_manager.get_session(request.session_id)
                if session:
                    session.update_activity()

            # Emit request event
            self._emit_event(
                InterfaceEventType.REQUEST_RECEIVED,
                {
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "interface_type": request.interface_type,
                    "user_id": request.user_id,
                }
            )

            # Call handler
            response = handler(request)

            # Emit response event
            self._emit_event(
                InterfaceEventType.RESPONSE_SENT,
                {
                    "request_id": response.request_id,
                    "status": response.status,
                }
            )

            return response

        except Exception as e:
            self.logger.error("Error processing request %s: %s", request.request_id, e)
            # Do NOT expose raw exception class names or tracebacks to the user
            return Response(
                request_id=request.request_id,
                status="error",
                message="Something went wrong while processing your request. Please try again.",
            )
    
    def create_session(
        self,
        user_id: str,
        interface_type: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new session.
        
        Args:
            user_id: User ID
            interface_type: Interface type
            context: Optional context data
            
        Returns:
            Session ID
        """
        with self._lock:
            session = self.session_manager.create_session(
                user_id=user_id,
                interface_type=interface_type,
                context=context,
            )
            
            self._emit_event(
                InterfaceEventType.SESSION_CREATED,
                {
                    "session_id": session.session_id,
                    "user_id": user_id,
                    "interface_type": interface_type,
                }
            )
            
            return session.session_id
    
    def close_session(self, session_id: str) -> bool:
        """
        Close a session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            True if closed, False if not found
        """
        with self._lock:
            result = self.session_manager.close_session(session_id)
            if result:
                self._emit_event(
                    InterfaceEventType.SESSION_CLOSED,
                    {"session_id": session_id}
                )
            return result
    
    def status(self) -> dict[str, Any]:
        """
        Get current interface status.
        
        Returns:
            Status dictionary
        """
        with self._lock:
            return {
                "is_running": self._is_running,
                "interfaces_total": self.registry.count(),
                "interfaces_available": self.registry.count_available(),
                "active_sessions": self.session_manager.session_count(),
                "interfaces": [
                    {
                        "name": i.name,
                        "type": i.interface_type,
                        "running": i.is_running,
                    }
                    for i in self.registry.list_all()
                ],
            }
    
    # --- Public API (Unified Contract) ---

    def register(self, interface: Interface) -> None:
        """Alias for register_interface to match milestone Public API."""
        self.register_interface(interface)

    def start(self, interface_type: Optional[str] = None) -> Any:
        """Start a specific interface or all interfaces to match milestone Public API."""
        if interface_type:
            self.start_interface(interface_type)
        else:
            self.start_all()

    def stop(self, interface_type: Optional[str] = None) -> Any:
        """Stop a specific interface or all interfaces to match milestone Public API."""
        if interface_type:
            self.stop_interface(interface_type)
        else:
            self.stop_all()

    def send(self, response: Response) -> None:
        """Route and send response back to the appropriate interface."""
        with self._lock:
            interface_type = self._request_interfaces.pop(response.request_id, None)
            if not interface_type:
                # Fallback: check session manager for the session owner's interface type
                session_id = response.metadata.get("session_id") if response.metadata else None
                if session_id:
                    session = self.session_manager.get_session(session_id)
                    if session:
                        interface_type = session.interface_type
            
            if interface_type:
                interface = self.registry.get(interface_type)
                if interface:
                    interface.send(response)
                    self._emit_event(
                        InterfaceEventType.RESPONSE_SENT,
                        {
                            "request_id": response.request_id,
                            "status": response.status,
                            "interface_type": interface_type
                        }
                    )
                    return
            
            # Broadcast to all running interfaces if routing is unknown
            for interface in self.registry.list_all():
                if interface.is_running:
                    interface.send(response)

    def receive(self, interface_type: Optional[str] = None) -> Optional[Request]:
        """Receive request from a specific interface or poll all running interfaces."""
        with self._lock:
            if interface_type:
                interface = self.registry.get(interface_type)
                if interface and interface.is_running:
                    return interface.receive()
                return None
            
            for interface in self.registry.list_all():
                if interface.is_running:
                    request = interface.receive()
                    if request:
                        return request
            return None

    def sessions(self) -> list[Any]:
        """List all active sessions."""
        return self.session_manager.list_sessions()

    def interfaces(self) -> list[Interface]:
        """List all registered interfaces."""
        return self.registry.list_all()

    # --- Internal helpers ---
    
    def _emit_event(self, name: str, payload: dict[str, Any]) -> None:
        """
        Emit an event.
        
        Args:
            name: Event name
            payload: Event payload
        """
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="interfaces.manager",
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Failed to emit event %s: %s", name, e)

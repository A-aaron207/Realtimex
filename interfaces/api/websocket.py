"""
WebSocket Interface for Realtimex.

Provides WebSocket API for real-time communication using standard library sockets.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import socket
import threading
import uuid
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Optional

from interfaces.base import Interface, Request, Response
from interfaces.exceptions import InterfaceInitializationError

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def handle_handshake(sock: socket.socket) -> Optional[str]:
    """Perform WebSocket handshake with connecting client."""
    request_data = b""
    while b"\r\n\r\n" not in request_data:
        try:
            chunk = sock.recv(1024)
            if not chunk:
                break
            request_data += chunk
            if len(request_data) > 8192:
                break
        except Exception:
            break
            
    if not request_data:
        return None
        
    request_str = request_data.decode('utf-8', errors='ignore')
    lines = request_str.split("\r\n")
    
    # Extract Sec-WebSocket-Key
    ws_key = None
    for line in lines:
        if line.lower().startswith("sec-websocket-key:"):
            ws_key = line.split(":", 1)[1].strip()
            break
            
    if not ws_key:
        return None
        
    # Calculate accept key
    accept_val = base64.b64encode(
        hashlib.sha1((ws_key + GUID).encode('utf-8')).digest()
    ).decode('utf-8')
    
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
    )
    sock.sendall(response.encode('utf-8'))
    return ws_key


def make_text_frame(message: str) -> bytes:
    """Construct a WebSocket text frame from a string."""
    data = message.encode('utf-8')
    length = len(data)
    if length <= 125:
        header = bytes([0x81, length])
    elif length <= 65535:
        header = bytes([0x81, 126]) + length.to_bytes(2, byteorder='big')
    else:
        header = bytes([0x81, 127]) + length.to_bytes(8, byteorder='big')
    return header + data


def read_text_frame(sock: socket.socket) -> Optional[str]:
    """Read and decode a masked WebSocket text frame from a socket."""
    header = sock.recv(2)
    if not header or len(header) < 2:
        return None
    
    fin_opcode = header[0]
    mask_length = header[1]
    
    # Opcode 1 represents text frame. Opcode 8 represents connection close.
    opcode = fin_opcode & 0x0f
    if opcode == 8:
        return None
        
    masked = (mask_length & 0x80) != 0
    length = mask_length & 0x7f
    
    if length == 126:
        len_bytes = sock.recv(2)
        if len(len_bytes) < 2:
            return None
        length = int.from_bytes(len_bytes, byteorder='big')
    elif length == 127:
        len_bytes = sock.recv(8)
        if len(len_bytes) < 8:
            return None
        length = int.from_bytes(len_bytes, byteorder='big')
        
    if masked:
        mask_key = sock.recv(4)
        if len(mask_key) < 4:
            return None
        
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            return None
        payload += chunk
        
    if masked:
        unmasked = bytearray(length)
        for i in range(length):
            unmasked[i] = payload[i] ^ mask_key[i % 4]
        return unmasked.decode('utf-8')
    else:
        return payload.decode('utf-8')


class WebSocketInterface(Interface):
    """
    WebSocket interface for Realtimex.
    
    Supports:
    - Live task updates
    - Streaming model responses
    - Event notifications
    - Progress updates
    - Bidirectional communication
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8001,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize WebSocket Interface.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            logger: Optional logger instance
        """
        super().__init__(name="WebSocket", interface_type="websocket")
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger("realtimex.interfaces.websocket")
        self._connections: dict[str, socket.socket] = {}  # connection_id -> socket
        self._request_queue: Queue[Request] = Queue()
        self._lock = threading.RLock()
        self.server_socket: Optional[socket.socket] = None
        self.listen_thread: Optional[threading.Thread] = None

    def initialize(self) -> None:
        """Initialize WebSocket interface."""
        try:
            self.logger.info("WebSocket Interface initializing on %s:%d", self.host, self.port)
        except Exception as e:
            raise InterfaceInitializationError(f"WebSocket initialization failed: {e}") from e

    def start(self) -> None:
        """Start WebSocket interface."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.is_running = True
            
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            self.logger.info("WebSocket Interface started on ws://%s:%d", self.host, self.port)
        except Exception as e:
            self.logger.error("Failed to start WebSocket interface: %s", e)
            raise

    def _listen_loop(self) -> None:
        while self.is_running:
            try:
                client_sock, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.is_running:
                    self.logger.error("Error accepting WebSocket connection: %s", e)

    def _handle_client(self, client_sock: socket.socket, addr: tuple[str, int]) -> None:
        connection_id = str(uuid.uuid4())
        try:
            ws_key = handle_handshake(client_sock)
            if not ws_key:
                client_sock.close()
                return
                
            with self._lock:
                self._connections[connection_id] = client_sock
                
            self.logger.info("WebSocket client connected: %s from %s", connection_id, addr)
            self._emit_event("ClientConnected", {"client_id": connection_id, "address": f"{addr[0]}:{addr[1]}"})
            
            client_sock.settimeout(1.0)
            while self.is_running:
                try:
                    message = read_text_frame(client_sock)
                    if message is None:
                        # Client disconnected
                        break
                        
                    # Process client message
                    try:
                        data = json.loads(message)
                        request = Request(
                            request_id=str(uuid.uuid4()),
                            session_id=data.get("session_id", connection_id),
                            timestamp=datetime.now(timezone.utc),
                            user_input=data,
                            interface_type=self.interface_type,
                            user_id=data.get("user_id", "websocket_user"),
                            metadata={"client_id": connection_id}
                        )
                        self._request_queue.put(request)
                        self.logger.debug("Received request from WS client %s", connection_id)
                    except json.JSONDecodeError:
                        self.logger.warning("WS client %s sent invalid JSON", connection_id)
                        error_resp = {
                            "status": "error",
                            "message": "Invalid JSON frame received"
                        }
                        client_sock.sendall(make_text_frame(json.dumps(error_resp)))
                except socket.timeout:
                    continue
                except socket.error as e:
                    self.logger.debug("Socket error on connection %s: %s", connection_id, e)
                    break
        except Exception as e:
            self.logger.error("Exception handling WS client %s: %s", connection_id, e)
        finally:
            with self._lock:
                if connection_id in self._connections:
                    del self._connections[connection_id]
            try:
                client_sock.close()
            except Exception:
                pass
            self.logger.info("WebSocket client disconnected: %s", connection_id)
            self._emit_event("ClientDisconnected", {"client_id": connection_id})

    def stop(self) -> None:
        """Stop WebSocket interface."""
        self.is_running = False
        with self._lock:
            for client_sock in list(self._connections.values()):
                try:
                    client_sock.close()
                except Exception:
                    pass
            self._connections.clear()
            
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.logger.info("WebSocket Interface stopped")

    def shutdown(self) -> None:
        """Shutdown WebSocket interface."""
        self.stop()

    def receive(self) -> Optional[Request]:
        """
        Receive request from WebSocket client.
        
        Returns:
            Request object or None if no requests pending
        """
        try:
            return self._request_queue.get(block=False)
        except Empty:
            return None

    def send(self, response: Response) -> None:
        """
        Send response to WebSocket clients.
        
        Args:
            response: Response object to send
        """
        try:
            target_client_id = response.metadata.get("client_id")
            message = json.dumps(response.to_dict(), default=str)
            frame = make_text_frame(message)
            
            with self._lock:
                if target_client_id and target_client_id in self._connections:
                    try:
                        self._connections[target_client_id].sendall(frame)
                    except Exception as e:
                        self.logger.warning("Failed to send frame to client %s: %s", target_client_id, e)
                else:
                    # Broadcast to all connected clients
                    for client_id, client_sock in list(self._connections.items()):
                        try:
                            client_sock.sendall(frame)
                        except Exception as e:
                            self.logger.warning("Failed to send frame to client %s: %s", client_id, e)
            
            self.logger.debug("Response sent to WebSocket clients")
        except Exception as e:
            self.logger.error("Error sending WebSocket response: %s", e)

    def connect(self, connection_id: str) -> None:
        """
        Register a new connection mock (for compatibility/testing).
        
        Args:
            connection_id: Unique connection identifier
        """
        with self._lock:
            # We insert a mock dummy socket mapping to keep track
            self._connections[connection_id] = socket.socket()  # dummy socket
            self.logger.info("Mock WebSocket connection established: %s", connection_id)
            self._emit_event("ClientConnected", {"client_id": connection_id})

    def disconnect(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            connection_id: Connection ID to disconnect
        """
        with self._lock:
            if connection_id in self._connections:
                sock = self._connections.pop(connection_id)
                try:
                    sock.close()
                except Exception:
                    pass
                self.logger.info("WebSocket connection closed: %s", connection_id)
                self._emit_event("ClientDisconnected", {"client_id": connection_id})

    def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Broadcast an event to all connected clients.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            message = json.dumps({
                "type": "event",
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            frame = make_text_frame(message)
            
            with self._lock:
                for client_sock in list(self._connections.values()):
                    try:
                        client_sock.sendall(frame)
                    except Exception:
                        pass
            
            self.logger.debug("Event broadcasted to WebSocket clients: %s", event_type)
        except Exception as e:
            self.logger.error("Error broadcasting event: %s", e)

    def connection_count(self) -> int:
        """Get number of active connections."""
        with self._lock:
            return len(self._connections)

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Helper to emit event to InterfaceManager or directly to EventBus."""
        if hasattr(self, 'manager') and self.manager:
            self.manager._emit_event(event_type, data)
        elif hasattr(self, 'event_bus') and self.event_bus:
            try:
                from events.event import Event, EventPriority
                self.event_bus.emit(
                    Event(
                        name=event_type,
                        source="interfaces.websocket",
                        priority=EventPriority.NORMAL,
                        payload=data,
                    )
                )
            except Exception as e:
                self.logger.warning("Failed to emit event %s: %s", event_type, e)

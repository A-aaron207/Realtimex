"""
CLI Interface for Realtimex.

Provides command-line interface for user interaction.
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from interfaces.base import Interface, Request, Response
from interfaces.exceptions import InterfaceInitializationError
from interfaces.cli.parser import CLIParser


class CLIInterface(Interface):
    """
    Command-line interface for Realtimex.
    
    Supports:
    - Interactive mode (continuous command loop)
    - Single-command mode (execute one command and exit)
    - Colored output (optional)
    - Progress updates
    - Streaming responses
    """

    def __init__(
        self,
        user_id: str = "cli_user",
        interactive: bool = True,
        single_command: Optional[str] = None,
        use_colors: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize CLI Interface.
        
        Args:
            user_id: User ID for CLI sessions
            interactive: Whether to run in interactive mode
            single_command: Optional single command string to execute
            use_colors: Whether to use colored ANSI output
            logger: Optional logger instance
        """
        super().__init__(name="CLI", interface_type="cli")
        self.user_id = user_id
        self.interactive = interactive
        self.single_command = single_command
        self.use_colors = use_colors
        self.logger = logger or logging.getLogger("realtimex.interfaces.cli")
        self.session_id: Optional[str] = None
        self._pending_requests: list[Request] = []
        self._parser = CLIParser()
        self._single_command_run = False

    def initialize(self) -> None:
        """Initialize CLI interface."""
        try:
            self.logger.info("CLI Interface initializing")
        except Exception as e:
            raise InterfaceInitializationError(f"CLI initialization failed: {e}") from e

    def start(self) -> None:
        """Start CLI interface."""
        self.logger.info("CLI Interface starting")
        self.is_running = True

    def stop(self) -> None:
        """Stop CLI interface."""
        self.logger.info("CLI Interface stopping")
        self.is_running = False

    def shutdown(self) -> None:
        """Shutdown CLI interface."""
        self.logger.info("CLI Interface shutdown")
        self.is_running = False

    def receive(self) -> Optional[Request]:
        """
        Receive CLI command from user.
        
        Returns:
            Request object or None if no input
        """
        if self._pending_requests:
            return self._pending_requests.pop(0)
        
        try:
            command = None
            if self.interactive:
                prompt = f"[{self.user_id}]> "
                command = input(prompt)
            else:
                if not self._single_command_run:
                    command = self.single_command
                    self._single_command_run = True
                    # Fallback to sys.argv if no command provided in single_command
                    if not command and len(sys.argv) > 1:
                        command = " ".join(sys.argv[1:])
            
            if not command or not command.strip():
                return None
            
            # Parse command
            parsed = self._parser.parse_command(command)
            
            # Create request
            request = Request(
                request_id=str(uuid.uuid4()),
                session_id=self.session_id or str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                user_input=parsed,
                interface_type=self.interface_type,
                user_id=self.user_id,
            )
            
            return request
            
        except EOFError:
            # End of input
            return None
        except Exception as e:
            self.logger.error("Error receiving CLI command: %s", e)
            return None

    def send(self, response: Response) -> None:
        """
        Send response to CLI output.
        
        Args:
            response: Response object to send
        """
        try:
            status_color = "\033[32m"  # Green
            if response.status == "error":
                status_color = "\033[31m"  # Red
            elif response.status in ("pending", "queued", "running"):
                status_color = "\033[33m"  # Yellow
            
            if response.status == "streaming":
                # Streaming response chunk
                sys.stdout.write(response.message)
                sys.stdout.flush()
                return

            print(f"\n[Response ID: {self._color(response.request_id, '\033[36m')}]")
            print(f"Status: {self._color(response.status.upper(), status_color)}")
            
            # Progress bar
            progress = response.metadata.get("progress")
            if progress is not None:
                try:
                    prog_val = int(progress)
                    print(f"Progress: {self._draw_progress(prog_val)}")
                except (ValueError, TypeError):
                    pass

            if response.message:
                print(f"Message: {response.message}")
            
            if response.data:
                print(f"Data: {response.data}")
            
            if response.artifacts:
                print(self._color("Artifacts:", "\033[1m\033[34m"))
                for artifact in response.artifacts:
                    print(f"  - {artifact}")
            
            if response.events:
                print(self._color("Events:", "\033[1m\033[34m"))
                for event in response.events:
                    print(f"  - {event}")
            
            print()  # Blank line for readability
            
        except Exception as e:
            self.logger.error("Error sending CLI response: %s", e)

    def set_session(self, session_id: str) -> None:
        """
        Set session ID for subsequent requests.
        
        Args:
            session_id: Session ID to use
        """
        self.session_id = session_id
        self.logger.debug("CLI session set: %s", session_id)

    def _color(self, text: str, color_code: str) -> str:
        """Wrap text in ANSI color codes if colors are enabled."""
        if self.use_colors:
            return f"{color_code}{text}\033[0m"
        return text

    def _draw_progress(self, progress: int) -> str:
        """Render an ANSI progress bar."""
        bar_length = 20
        filled_length = int(round(bar_length * progress / 100))
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"[{progress}%] [{bar}]"

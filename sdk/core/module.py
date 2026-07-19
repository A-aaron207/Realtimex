"""
Base Module and ModuleContext for Realtimex MDK.

Defines the safe sandbox APIs and parent classes for modules.
"""

from __future__ import annotations

from typing import Any, Optional


class ModuleContext:
    """
    Exposes safe, structured interfaces to modules for interacting with
    the Kernel, preventing direct access to internal state.
    """

    def __init__(
        self,
        event_bus: Any = None,
        memory: Any = None,
        config: Any = None,
        logging: Any = None,
        models: Any = None,
        permissions: Any = None,
        tasks: Any = None,
    ) -> None:
        self._bus = event_bus
        self._memory = memory
        self._config = config
        self._logging = logging
        self._models = models
        self._permissions = permissions
        self._tasks = tasks

    def publish_event(self, event: Any) -> None:
        """Publish event to Event Bus."""
        if self._bus:
            self._bus.publish(event)

    def subscribe_event(self, event_name: str, callback: Any) -> None:
        """Subscribe to events on the Event Bus."""
        if self._bus:
            self._bus.subscribe(event_name, callback)

    def read_memory(self, key: str) -> Any:
        """Read value from Memory System."""
        if self._memory:
            return self._memory.get(key)
        return None

    def write_memory(self, key: str, value: Any) -> None:
        """Write value to Memory System."""
        if self._memory:
            self._memory.set(key, value)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Query configuration value."""
        if self._config:
            return self._config.get(key, default)
        return default

    def log(self, level: str | int, message: str, context: Optional[dict[str, Any]] = None) -> None:
        """Log structured log message."""
        if self._logging:
            self._logging.log(level, message, context)

    def call_model(self, prompt: str, **kwargs: Any) -> Any:
        """Invoke Model Gateway text generation."""
        if self._models:
            return self._models.generate(prompt, **kwargs)
        return None

    def check_permission(self, action: str, resource: str) -> bool:
        """Check if action is permitted on target resource."""
        if self._permissions:
            return self._permissions.check_permission(action, resource)
        return False

    def query_task(self, task_id: str) -> Any:
        """Retrieve task details from Task System."""
        if self._tasks:
            return self._tasks.get_task(task_id)
        return None


class BaseModule:
    """Abstract base class for all Realtimex Modules."""

    def __init__(self, context: ModuleContext) -> None:
        """
        Initialize Module.
        
        Args:
            context: Safe Sandbox ModuleContext
        """
        self.context = context

    def initialize(self) -> None:
        """Lifecycle hook executed upon loading the module."""
        pass

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Main execution method to implement."""
        raise NotImplementedError("Modules must implement the execute method.")

    def shutdown(self) -> None:
        """Lifecycle hook executed upon unloading the module."""
        pass

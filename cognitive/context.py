"""
Context builder for collecting reasoning state for the Realtimex Cognitive Engine.
"""

from __future__ import annotations

from typing import Any, Callable

from cognitive.exceptions import ContextBuilderError


class ContextBuilder:
    """
    Assembles contextual information from tasks, workflows, system configurations,
    sandbox permissions, and event history to build a unified context for reasoning.
    """

    def __init__(
        self,
        task_manager: Any = None,
        workflow_manager: Any = None,
        capability_registry: Any = None,
        event_manager: Any = None,
        loaded_modules_provider: Callable[[], list[Any]] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the ContextBuilder.

        Args:
            task_manager: The task manager to fetch tasks.
            workflow_manager: The workflow manager to fetch workflows.
            capability_registry: The capability registry to fetch registered capabilities.
            event_manager: The event manager to query previous decision events.
            loaded_modules_provider: Callable returning the list of loaded modules.
            config: General configuration dictionary.
        """
        self.task_manager = task_manager
        self.workflow_manager = workflow_manager
        self.capability_registry = capability_registry
        self.event_manager = event_manager
        self.loaded_modules_provider = loaded_modules_provider
        self.config = config or {}

    def build_context(
        self,
        task_id: str,
        workflow_id: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build a single reasoning context containing all gathered information.

        Args:
            task_id: The ID of the task to reason about.
            workflow_id: The optional ID of the workflow to reason about.
            additional_context: Explicit context passed by the caller.

        Returns:
            A dictionary representing the unified context for the reasoning pipeline.

        Raises:
            ContextBuilderError: If required context cannot be fetched due to underlying errors.
        """
        context: dict[str, Any] = {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "task": {},
            "workflow": {},
            "memory": {},
            "permissions": {},
            "configuration": self.config,
            "previous_decisions": [],
            "available_capabilities": [],
        }

        # 1. Fetch Task Context
        task_obj = None
        if self.task_manager is not None:
            try:
                task_obj = self.task_manager.get_task(task_id)
                context["task"] = task_obj.to_dict()
                # Populate memory from task by default
                if hasattr(task_obj, "memory") and task_obj.memory:
                    context["memory"].update(task_obj.memory)
            except Exception as e:
                raise ContextBuilderError(f"Context builder failed to retrieve task '{task_id}': {e}") from e

        # 2. Fetch Workflow Context
        if workflow_id and self.workflow_manager is not None:
            try:
                workflow_obj = self.workflow_manager.load_workflow(workflow_id)
                context["workflow"] = workflow_obj.to_dict()
            except Exception as e:
                raise ContextBuilderError(f"Context builder failed to retrieve workflow '{workflow_id}': {e}") from e
        elif task_obj is not None:
            # Try to infer workflow from task metadata/fields
            if hasattr(task_obj, "workflow") and isinstance(task_obj.workflow, dict) and task_obj.workflow:
                context["workflow"] = task_obj.workflow
                if "workflow_id" in task_obj.workflow:
                    context["workflow_id"] = task_obj.workflow["workflow_id"]

        # 3. Retrieve Memory & Additional Context
        if additional_context:
            if "memory" in additional_context and isinstance(additional_context["memory"], dict):
                context["memory"].update(additional_context["memory"])
            # Merge other additional context keys
            for k, v in additional_context.items():
                if k != "memory":
                    context[k] = v

        # 4. Fetch Capability List
        if self.capability_registry is not None:
            try:
                context["available_capabilities"] = self.capability_registry.list_capabilities()
            except Exception:
                pass

        # 5. Fetch Permissions block from loaded modules
        if self.loaded_modules_provider is not None:
            try:
                modules = self.loaded_modules_provider()
                permissions_map = {}
                for mod in modules:
                    if hasattr(mod, "manifest"):
                        manifest = mod.manifest
                        perms = getattr(manifest, "permissions", None)
                        if perms is not None:
                            permissions_map[manifest.module_id] = {
                                "filesystem": getattr(perms, "filesystem", "none"),
                                "network": getattr(perms, "network", False),
                                "terminal": getattr(perms, "terminal", False),
                                "memory": getattr(perms, "memory", "none"),
                                "capabilities": getattr(manifest, "capabilities", []),
                            }
                context["permissions"] = permissions_map
            except Exception:
                pass

        # 6. Query Previous Decisions (from Event History)
        if self.event_manager is not None:
            try:
                # Query all events matching the task ID
                matched_events = self.event_manager.filter_events(task_id=task_id)
                
                cognitive_event_types = {
                    "ReasoningStarted",
                    "ReasoningCompleted",
                    "DecisionGenerated",
                    "ValidationFailed",
                    "RecommendationAccepted",
                    "RecommendationRejected",
                }
                
                for event in matched_events:
                    if event.event_type in cognitive_event_types:
                        context["previous_decisions"].append({
                            "event_id": event.event_id,
                            "event_type": event.event_type,
                            "timestamp": event.timestamp.isoformat(),
                            "payload": event.payload,
                        })
            except Exception:
                # Context building should be resilient if event manager queries fail
                pass

        return context

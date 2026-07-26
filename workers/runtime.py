"""
Worker Runtime implementation executing capability modules dynamically.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
import os
from typing import Any, Callable

from events.event import Event
from loader.loader import LoadedModule
from workers.base import BaseWorker
from workers.context import ExecutionContext
from workers.exceptions import WorkerExecutionError
from workers.lifecycle import WorkerState
from workers.report import WorkerReport, WorkerReportStatus


class WorkerRuntime(BaseWorker):
    """
    A concrete worker implementation that loads a loaded capability module
    instance dynamically, executes the capability, and compiles reports.
    """

    def __init__(
        self,
        worker_id: str,
        worker_type: str,
        supported_capability: str,
        event_bus: Any,  # Avoid circular import, type hint dynamically
        module_resolver: Callable[[str], LoadedModule | None],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the Worker Runtime.

        Args:
            worker_id: Unique identifier.
            worker_type: e.g. "agent_worker".
            supported_capability: Capability this worker handles.
            event_bus: Global EventBus or EventManager to publish events.
            module_resolver: Callback resolving a module_id to a LoadedModule.
            metadata: Custom metadata dictionary.
        """
        super().__init__(worker_id, worker_type, supported_capability, metadata)
        self._event_bus = event_bus
        self._module_resolver = module_resolver

    def execute(self, context: ExecutionContext) -> WorkerReport:
        """
        Execute the step described by the context, transitioning lifecycle states,
        measuring performance, catching errors, and emitting bus events.

        Args:
            context: Immutable ExecutionContext with inputs.

        Returns:
            WorkerReport mapping outputs and status.
        """
        with self._lock:
            # 1. State updates
            if self.state != WorkerState.ASSIGNED:
                self.set_state(WorkerState.ASSIGNED)

            self.current_task_id = context.task_id
            self.current_step_id = context.step_id

            # Emit WorkerAssigned
            self._event_bus.publish(
                Event(
                    name="WorkerAssigned",
                    source="workers.runtime",
                    task_id=context.task_id,
                    payload={"worker_id": self.worker_id, "step_id": context.step_id},
                )
            )

            # Move state to RUNNING
            self.set_state(WorkerState.RUNNING)

            # Emit WorkerExecutionStarted
            self._event_bus.publish(
                Event(
                    name="WorkerExecutionStarted",
                    source="workers.runtime",
                    task_id=context.task_id,
                    payload={"worker_id": self.worker_id, "step_id": context.step_id},
                )
            )

        start_time_perf = time.perf_counter()
        warnings: list[str] = []
        artifacts: list[dict[str, Any]] = []
        output_data: dict[str, Any] = {}

        # Resolve any dynamic output references in context.input
        resolved_input = dict(context.input)
        for key, val in resolved_input.items():
            if isinstance(val, str) and val.startswith("Process ") and val.endswith(" output"):
                dep_step_id = val[8:-7].strip()
                try:
                    from services.registry import ServiceRegistry
                    reg = ServiceRegistry.get_instance()
                    wf_engine = reg.get("workflow_manager")
                    if wf_engine:
                        wf_mgr = wf_engine.metadata["manager"]
                        workflow = wf_mgr.load_workflow(context.workflow_id)
                        dep_step = workflow.steps.get(dep_step_id)
                        
                        # Cross-task fallback if step is not in the current workflow
                        if (not dep_step or not dep_step.output_data) and hasattr(reg, "get"):
                            try:
                                task_engine = reg.get("task_manager")
                                if task_engine:
                                    task_mgr = task_engine.metadata["manager"]
                                    current_task = task_mgr.get_task(context.task_id)
                                    session_id = current_task.metadata.get("session_id")
                                    if session_id:
                                        all_tasks = task_mgr._repository.find_by(
                                            lambda t: t.metadata.get("session_id") == session_id
                                        )
                                        sorted_tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)
                                        for t in sorted_tasks:
                                            if t.task_id == context.task_id:
                                                continue
                                            target_wf = None
                                            with wf_mgr._lock:
                                                for cached_wf in wf_mgr._cache.values():
                                                    if cached_wf.parent_task_id == t.task_id:
                                                        target_wf = cached_wf
                                                        break
                                            if not target_wf:
                                                all_wfs = wf_mgr._persistence.load_all()
                                                for persisted_wf in all_wfs:
                                                    if persisted_wf.parent_task_id == t.task_id:
                                                        target_wf = persisted_wf
                                                        break
                                            if target_wf:
                                                matching_step = target_wf.steps.get(dep_step_id)
                                                if not matching_step:
                                                    # Match by capability prefix/match
                                                    for step in target_wf.steps.values():
                                                        if (step.capability == dep_step_id or 
                                                            (dep_step_id in ("code_gen", "code", "generate_code") and step.capability == "generate_code") or 
                                                            (dep_step_id in ("summarize", "summarize_text") and step.capability == "summarize_text")):
                                                            matching_step = step
                                                            break
                                                if matching_step and matching_step.output_data:
                                                    dep_step = matching_step
                                                    break
                            except Exception as ex:
                                self._logger.warning("Error resolving cross-task session variables: %s", ex)
                                
                        if dep_step and dep_step.output_data:
                            # Extract string output from output_data
                            output_val = (
                                dep_step.output_data.get("output")
                                or dep_step.output_data.get("code")
                                or dep_step.output_data.get("summary")
                                or dep_step.output_data.get("results")
                                or str(dep_step.output_data)
                            )
                            resolved_input[key] = output_val
                except Exception as e:
                    self._logger.debug("Failed to resolve step parameter %s -> %s: %s", key, val, e)

        # Reconstruct context with resolved input
        context = ExecutionContext(
            task_id=context.task_id,
            workflow_id=context.workflow_id,
            step_id=context.step_id,
            capability=context.capability,
            input=resolved_input,
            memory_reference=context.memory_reference,
            configuration=context.configuration,
            permissions=context.permissions,
            metadata=context.metadata,
        )

        try:
            # Check resolved input for unresolved variable references
            for key, val in resolved_input.items():
                if isinstance(val, str):
                    if (val.startswith("Process ") and val.endswith(" output")) or ("{{" in val and "}}" in val):
                        raise WorkerExecutionError(
                            f"Variable resolution failed: parameter '{key}' contains unresolved reference '{val}'."
                        )

            # Path and permission validation for file writing
            if context.capability == "write_file":
                file_path = resolved_input.get("path") or resolved_input.get("file_path")
                if file_path:
                    abs_path = os.path.abspath(os.path.expanduser(file_path))
                    # 1. Prevent accidental overwrite of critical files
                    critical_prefixes = ("/etc", "/bin", "/sbin", "/usr", "/var", "/sys", "/proc", "/boot", "/dev", "/lib", "/lib64")
                    if abs_path.startswith(critical_prefixes):
                        raise WorkerExecutionError(f"Security violation: writing to system critical path '{abs_path}' is blocked.")
                    
                    # 2. Validate folder write permissions
                    dir_path = os.path.dirname(abs_path)
                    if os.path.exists(dir_path):
                        if not os.access(dir_path, os.W_OK):
                            raise WorkerExecutionError(f"Permission denied: directory '{dir_path}' is not writable.")
                    else:
                        # Check parent directory permissions recursively
                        parent = dir_path
                        while parent and parent != os.path.dirname(parent):
                            if os.path.exists(parent):
                                if not os.access(parent, os.W_OK):
                                    raise WorkerExecutionError(f"Permission denied: parent directory '{parent}' is not writable.")
                                break
                            parent = os.path.dirname(parent)

            # Check if the operation is destructive and request permission if so
            is_destructive = False
            action = context.capability
            target = resolved_input.get("path") or resolved_input.get("file_path") or resolved_input.get("command") or resolved_input.get("source") or ""
            
            # Check filesystem deletion or overwrite
            if context.capability in ("delete", "remove", "rm", "rmdir"):
                is_destructive = True
            elif context.capability == "write_file":
                # Check if file exists -> representing an overwrite
                file_path = resolved_input.get("path") or resolved_input.get("file_path")
                if file_path and os.path.exists(os.path.abspath(os.path.expanduser(file_path))):
                    is_destructive = True
                    action = "overwrite"
            elif context.capability == "run_command":
                cmd = resolved_input.get("command", "").lower()
                if any(term in cmd for term in ("rm ", "rmdir ", "remove ", "delete ", "move to trash", "recursive delete")):
                    is_destructive = True
                    action = "destructive_command"

            if is_destructive:
                from services.registry import ServiceRegistry
                reg = ServiceRegistry.get_instance()
                if reg.exists("permission_manager"):
                    perm_mgr = reg.get("permission_manager").metadata["manager"]
                    decision = perm_mgr.request(
                        task_id=context.task_id,
                        worker_id=self.worker_id,
                        action=action,
                        target=str(target),
                        requested_capability=context.capability,
                        risk_level="critical",
                        workflow_id=context.workflow_id
                    )
                    if not decision.approved:
                        raise WorkerExecutionError(f"Action denied: {decision.reason}")
            # 2. Resolve capability module
            # We assume the scheduler matched capabilities. We query the resolver
            # to fetch the concrete LoadedModule.
            module_id = context.configuration.get("provider_id")
            if not module_id:
                raise WorkerExecutionError(
                    f"Execution Context is missing 'provider_id' in configuration."
                )

            loaded_module = self._module_resolver(module_id)
            if not loaded_module:
                raise WorkerExecutionError(f"Module '{module_id}' is not loaded in Kernel.")

            # 3. Invoke capability method dynamically
            module_instance = loaded_module.instance
            capability_name = context.capability

            # Prioritize standardized execution contract
            if hasattr(module_instance, "execute") and callable(getattr(module_instance, "execute")):
                self._logger.debug("Executing capability via standardized contract: %s.execute(%r)", module_id, capability_name)
                try:
                    try:
                        output_data = module_instance.execute(capability_name, context)
                    except TypeError:
                        try:
                            output_data = module_instance.execute(context)
                        except TypeError:
                            output_data = module_instance.execute(capability_name, context.input)
                except NotImplementedError:
                    self._logger.warning(
                        "Module '%s' raised NotImplementedError for capability '%s'. Simulating execution...",
                        module_id,
                        capability_name,
                    )
                    output_data = self._simulate_fallback(capability_name, context.input)
                    warnings.append(f"Simulated execution. Method '{capability_name}' not implemented in module.")
            elif hasattr(module_instance, capability_name):
                method = getattr(module_instance, capability_name)
                if callable(method):
                    self._logger.debug("Executing capability method: %s.%s()", module_id, capability_name)
                    try:
                        output_data = method(context.input)
                    except TypeError:
                        output_data = method(context)
                else:
                    raise WorkerExecutionError(
                        f"Module attribute '{capability_name}' is not callable."
                    )
            else:
                # 4. Fallback execution simulation
                # Enables Milestone 6 to demonstrate modules that do not implement execution code yet.
                self._logger.warning(
                    "Module '%s' does not implement method for capability '%s'. Simulating execution...",
                    module_id,
                    capability_name,
                )
                output_data = self._simulate_fallback(capability_name, context.input)
                warnings.append(f"Simulated execution. Method '{capability_name}' not implemented in module.")

            # Capture mock artifacts for realistic outputs in demo
            if "artifacts" in output_data and isinstance(output_data["artifacts"], list):
                artifacts.extend(output_data["artifacts"])

            # 5. Reporting Phase
            with self._lock:
                self.set_state(WorkerState.REPORTING)

            exec_time = time.perf_counter() - start_time_perf

            report = WorkerReport(
                status=WorkerReportStatus.SUCCESS,
                worker_id=self.worker_id,
                task_id=context.task_id,
                step_id=context.step_id,
                output=output_data,
                artifacts=artifacts,
                warnings=warnings,
                metrics={"execution_time": round(exec_time, 3)},
            )

            # Emit WorkerReportGenerated
            self._event_bus.publish(
                Event(
                    name="WorkerReportGenerated",
                    source="workers.runtime",
                    task_id=context.task_id,
                    payload=report.to_dict(),
                )
            )

            # Emit WorkerExecutionFinished
            self._event_bus.publish(
                Event(
                    name="WorkerExecutionFinished",
                    source="workers.runtime",
                    task_id=context.task_id,
                    payload={"worker_id": self.worker_id, "status": "SUCCESS"},
                )
            )

            # Move state back to IDLE
            with self._lock:
                self.set_state(WorkerState.IDLE)
                self.current_task_id = None
                self.current_step_id = None

            return report

        except Exception as e:
            # Handle execution failure
            self._logger.exception("Error executing step %s", context.step_id)
            exec_time = time.perf_counter() - start_time_perf

            with self._lock:
                self.set_state(WorkerState.FAILED)

            # Emit WorkerFailed
            self._event_bus.publish(
                Event(
                    name="WorkerFailed",
                    source="workers.runtime",
                    task_id=context.task_id,
                    payload={"worker_id": self.worker_id, "step_id": context.step_id, "reason": str(e)},
                )
            )

            report = WorkerReport(
                status=WorkerReportStatus.FAILED,
                worker_id=self.worker_id,
                task_id=context.task_id,
                step_id=context.step_id,
                metrics={"execution_time": round(exec_time, 3)},
                error_message=str(e),
            )

            # Recover back to idle
            with self._lock:
                self.set_state(WorkerState.RECOVERING)
                # Emit WorkerRecovered
                self._event_bus.publish(
                    Event(
                        name="WorkerRecovered",
                        source="workers.runtime",
                        task_id=context.task_id,
                        payload={"worker_id": self.worker_id},
                    )
                )
                self.set_state(WorkerState.IDLE)
                self.current_task_id = None
                self.current_step_id = None

            return report

    def _simulate_fallback(self, capability: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Provide simulated outputs/artifacts based on the capability name."""
        if capability == "plan_task":
            return {
                "scope_analysis": "Completed planning scope mapping.",
                "complexity": "medium",
                "artifacts": [{"name": "project_outline.md", "type": "markdown"}],
            }
        elif capability == "web_search":
            return {
                "results": ["Mock search result 1", "Mock search result 2"],
                "query_processed": input_data.get("query", ""),
                "artifacts": [],
            }
        elif capability == "generate_image":
            return {
                "image_path": "logs/artifacts/portfolio_mockup.png",
                "prompt": input_data.get("prompt", ""),
                "artifacts": [{"name": "portfolio_mockup.png", "type": "image"}],
            }
        elif capability == "write_file":
            return {
                "bytes_written": 1280,
                "file_path": input_data.get("file_path", "temp_file.txt"),
                "artifacts": [{"name": input_data.get("file_path", "temp_file.txt"), "type": "file"}],
            }
        elif capability == "read_file":
            return {
                "file_contents": "Mock file contents for verification.",
                "file_path": input_data.get("file_path", ""),
            }
        elif capability == "summarize_text":
            return {
                "summary": "Mock summary of build outputs.",
                "artifacts": [{"name": "build_summary.txt", "type": "text"}],
            }
        return {"status": "fallback_mock", "capability_run": capability, "input_received": input_data}

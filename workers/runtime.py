"""
Worker Runtime implementation executing capability modules dynamically.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
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

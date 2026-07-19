"""
Workflow Manager — orchestrator of execution plans, step graphs, and state updates.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from events.event import Event
from workflow.exceptions import WorkflowNotFoundError, WorkflowValidationError
from workflow.graph import DependencyGraph
from workflow.planner import RuleBasedWorkflowPlanner
from workflow.step import StepState, WorkflowStep, validate_step_transition
from workflow.validator import validate_workflow
from workflow.workflow import Workflow, WorkflowStatus

if TYPE_CHECKING:
    from events.bus import EventBus
    from workflow.persistence import WorkflowPersistence


class WorkflowManager:
    """
    Coordinates planning, modifying, and querying workflows.
    Ensures structural validation and emits workflow lifecycle events.
    """

    def __init__(
        self,
        persistence: WorkflowPersistence,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize Workflow Manager.

        Args:
            persistence: persistence layer for workflows.
            event_bus: Global event bus.
            logger: Diagnostics logger.
        """
        self._persistence = persistence
        self._event_bus = event_bus
        self._logger = logger
        self._lock = threading.RLock()
        self._cache: dict[str, Workflow] = {}
        self._planner = RuleBasedWorkflowPlanner()
        self._load_initial_cache()

    def _load_initial_cache(self) -> None:
        """Load all persisted workflows into cache."""
        try:
            all_wf = self._persistence.load_all()
            for wf in all_wf:
                self._cache[wf.workflow_id] = wf
        except Exception as e:
            self._logger.warning("Failed to initialize workflow cache: %s", e)

    def create_workflow(
        self,
        parent_task_id: str,
        goal: str,
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """
        Create a new workflow based on user goal, plan steps, and persist it.

        Args:
            parent_task_id: UUID of parent task.
            goal: Task goal.
            metadata: Custom metadata dictionary.

        Returns:
            The planned Workflow.
        """
        with self._lock:
            # 1. Instantiate workflow
            wf = Workflow(
                parent_task_id=parent_task_id,
                status=WorkflowStatus.PLANNING,
                metadata=metadata or {},
            )

            # 2. Plan steps
            planned_steps = self._planner.plan(wf.workflow_id, goal)
            steps_dict = {s.step_id: s for s in planned_steps}

            # Find root step (first step without dependencies, or planning step)
            root_id = None
            if "planning" in steps_dict:
                root_id = "planning"
            elif "analyze" in steps_dict:
                root_id = "analyze"
            elif planned_steps:
                # Fallback: first step with 0 in-degree
                roots = [s.step_id for s in planned_steps if not s.dependencies]
                if roots:
                    root_id = roots[0]

            wf = dataclasses.replace(
                wf,
                steps=steps_dict,
                root_step_id=root_id,
                status=WorkflowStatus.PLANNING_COMPLETE,
            )

            # 3. Validate structural sanity
            try:
                validate_workflow(wf)
                self._event_bus.publish(
                    Event(
                        name="WorkflowValidated",
                        source="workflow.manager",
                        task_id=parent_task_id,
                        payload={"workflow_id": wf.workflow_id},
                    )
                )
            except WorkflowValidationError as e:
                wf = dataclasses.replace(wf, status=WorkflowStatus.FAILED)
                self._event_bus.publish(
                    Event(
                        name="WorkflowFailed",
                        source="workflow.manager",
                        task_id=parent_task_id,
                        payload={"workflow_id": wf.workflow_id, "reason": str(e)},
                    )
                )
                raise

            # 4. Save and Cache
            self._cache[wf.workflow_id] = wf
            self._persistence.save(wf)

            # 5. Emit WorkflowCreated
            self._event_bus.publish(
                Event(
                    name="WorkflowCreated",
                    source="workflow.manager",
                    task_id=parent_task_id,
                    payload=wf.to_dict(),
                )
            )

            self._logger.info("Created workflow %s for task %s", wf.workflow_id, parent_task_id)
            return wf

    def load_workflow(self, workflow_id: str) -> Workflow:
        """
        Load a workflow by ID from cache or persistence.

        Args:
            workflow_id: UUID of workflow.

        Returns:
            The Workflow.

        Raises:
            WorkflowNotFoundError: If workflow is missing.
        """
        with self._lock:
            if workflow_id in self._cache:
                return self._cache[workflow_id]

            wf = self._persistence.load(workflow_id)
            if wf is None:
                raise WorkflowNotFoundError(f"Workflow with ID '{workflow_id}' not found.")
            
            self._cache[workflow_id] = wf
            return wf

    def save_workflow(self, workflow: Workflow) -> None:
        """Save workflow to cache and disk persistence."""
        with self._lock:
            # Increment version on update
            updated_wf = dataclasses.replace(workflow, version=workflow.version + 1)
            self._cache[updated_wf.workflow_id] = updated_wf
            self._persistence.save(updated_wf)

    def validate(self, workflow_id: str) -> bool:
        """
        Check structural validity of a workflow.

        Returns:
            True if valid, raises exception otherwise.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            validate_workflow(wf)
            return True

    def add_step(self, workflow_id: str, step: WorkflowStep) -> Workflow:
        """
        Dynamically add a step to the workflow.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step.step_id in wf.steps:
                raise WorkflowValidationError(f"Step with ID '{step.step_id}' already exists.")

            new_steps = dict(wf.steps)
            new_steps[step.step_id] = step

            updated_wf = dataclasses.replace(wf, steps=new_steps)

            # Validate graph integrity
            validate_workflow(updated_wf)

            self.save_workflow(updated_wf)

            # Emit events
            self._event_bus.publish(
                Event(
                    name="StepAdded",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id, "step": step.to_dict()},
                )
            )
            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )

            self._logger.info("Added step %s to workflow %s", step.step_id, workflow_id)
            return self._cache[workflow_id]

    def remove_step(self, workflow_id: str, step_id: str) -> Workflow:
        """
        Dynamically remove a step from the workflow.
        Removes step and updates any step dependencies referencing it.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step_id not in wf.steps:
                raise WorkflowNotFoundError(f"Step '{step_id}' not found in workflow '{workflow_id}'.")

            new_steps = dict(wf.steps)
            del new_steps[step_id]

            # Update dependencies of remaining steps to filter out the deleted step
            cleaned_steps = {}
            for sid, step in new_steps.items():
                if step_id in step.dependencies:
                    new_deps = frozenset(step.dependencies - {step_id})
                    cleaned_steps[sid] = dataclasses.replace(step, dependencies=new_deps)
                else:
                    cleaned_steps[sid] = step

            updated_wf = dataclasses.replace(wf, steps=cleaned_steps)

            # If root was deleted, find another root
            if updated_wf.root_step_id == step_id:
                roots = [s.step_id for s in cleaned_steps.values() if not s.dependencies]
                root_id = roots[0] if roots else None
                updated_wf = dataclasses.replace(updated_wf, root_step_id=root_id)

            validate_workflow(updated_wf)
            self.save_workflow(updated_wf)

            # Emit events
            self._event_bus.publish(
                Event(
                    name="StepRemoved",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id, "step_id": step_id},
                )
            )
            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )

            self._logger.info("Removed step %s from workflow %s", step_id, workflow_id)
            return self._cache[workflow_id]

    def replace_step(self, workflow_id: str, step_id: str, new_step: WorkflowStep) -> Workflow:
        """
        Replace a step with a new step specification.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step_id not in wf.steps:
                raise WorkflowNotFoundError(f"Step '{step_id}' not found in workflow '{workflow_id}'.")

            new_steps = dict(wf.steps)
            del new_steps[step_id]
            new_steps[new_step.step_id] = new_step

            # If step ID changed, update references
            if step_id != new_step.step_id:
                cleaned_steps = {}
                for sid, step in new_steps.items():
                    if step_id in step.dependencies:
                        new_deps = frozenset((step.dependencies - {step_id}) | {new_step.step_id})
                        cleaned_steps[sid] = dataclasses.replace(step, dependencies=new_deps)
                    else:
                        cleaned_steps[sid] = step
                new_steps = cleaned_steps

            updated_wf = dataclasses.replace(wf, steps=new_steps)
            if updated_wf.root_step_id == step_id:
                updated_wf = dataclasses.replace(updated_wf, root_step_id=new_step.step_id)

            validate_workflow(updated_wf)
            self.save_workflow(updated_wf)

            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )
            return self._cache[workflow_id]

    def merge_steps(
        self,
        workflow_id: str,
        step_ids: list[str],
        merged_step_id: str,
        merged_step_properties: dict[str, Any],
    ) -> Workflow:
        """
        Merge multiple steps into a single new step.
        Adapts dependencies accordingly.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            for sid in step_ids:
                if sid not in wf.steps:
                    raise WorkflowNotFoundError(f"Step '{sid}' not found in workflow '{workflow_id}'.")

            # Collect dependencies of steps to be merged, excluding each other
            merged_deps = set()
            for sid in step_ids:
                merged_deps.update(wf.steps[sid].dependencies)
            merged_deps = merged_deps - set(step_ids)

            # Create merged step
            new_step = WorkflowStep(
                step_id=merged_step_id,
                workflow_id=workflow_id,
                capability=merged_step_properties.get("capability", "plan_task"),
                input_data=merged_step_properties.get("input_data", {}),
                status=StepState.PENDING,
                dependencies=frozenset(merged_deps),
                estimated_time=sum(wf.steps[sid].estimated_time for sid in step_ids),
                estimated_cost=sum(wf.steps[sid].estimated_cost for sid in step_ids),
                metadata=merged_step_properties.get("metadata", {}),
            )

            # Build new steps collection
            new_steps = {sid: step for sid, step in wf.steps.items() if sid not in step_ids}
            new_steps[merged_step_id] = new_step

            # Redirect remaining steps' dependencies on any of the merged steps to the new merged step
            cleaned_steps = {}
            for sid, step in new_steps.items():
                if sid == merged_step_id:
                    cleaned_steps[sid] = step
                    continue

                if any(m_id in step.dependencies for m_id in step_ids):
                    new_deps = frozenset((step.dependencies - set(step_ids)) | {merged_step_id})
                    cleaned_steps[sid] = dataclasses.replace(step, dependencies=new_deps)
                else:
                    cleaned_steps[sid] = step

            updated_wf = dataclasses.replace(wf, steps=cleaned_steps)
            if updated_wf.root_step_id in step_ids:
                updated_wf = dataclasses.replace(updated_wf, root_step_id=merged_step_id)

            validate_workflow(updated_wf)
            self.save_workflow(updated_wf)

            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )
            return self._cache[workflow_id]

    def split_step(
        self,
        workflow_id: str,
        step_id_to_split: str,
        new_steps: list[WorkflowStep],
    ) -> Workflow:
        """
        Split a single step into multiple steps, executed sequentially.
        """
        if not new_steps:
            raise WorkflowValidationError("Must provide at least one replacement step for splitting.")

        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step_id_to_split not in wf.steps:
                raise WorkflowNotFoundError(f"Step '{step_id_to_split}' not found in workflow '{workflow_id}'.")

            original_step = wf.steps[step_id_to_split]

            # Re-map dependencies of the first new step to point to the original step's dependencies
            updated_new_steps = []
            for i, ns in enumerate(new_steps):
                if i == 0:
                    ns = dataclasses.replace(ns, dependencies=original_step.dependencies)
                else:
                    # Sequential link
                    ns = dataclasses.replace(ns, dependencies=frozenset([new_steps[i - 1].step_id]))
                updated_new_steps.append(ns)

            # Build new steps list
            new_steps_dict = {sid: step for sid, step in wf.steps.items() if sid != step_id_to_split}
            for ns in updated_new_steps:
                new_steps_dict[ns.step_id] = ns

            # Update dependencies of other steps: if they depended on step_id_to_split, they now depend on the last new step
            last_new_step_id = updated_new_steps[-1].step_id
            cleaned_steps = {}
            for sid, step in new_steps_dict.items():
                if sid in [ns.step_id for ns in updated_new_steps]:
                    cleaned_steps[sid] = step
                    continue

                if step_id_to_split in step.dependencies:
                    new_deps = frozenset((step.dependencies - {step_id_to_split}) | {last_new_step_id})
                    cleaned_steps[sid] = dataclasses.replace(step, dependencies=new_deps)
                else:
                    cleaned_steps[sid] = step

            updated_wf = dataclasses.replace(wf, steps=cleaned_steps)
            if updated_wf.root_step_id == step_id_to_split:
                updated_wf = dataclasses.replace(updated_wf, root_step_id=updated_new_steps[0].step_id)

            validate_workflow(updated_wf)
            self.save_workflow(updated_wf)

            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )
            return self._cache[workflow_id]

    def update_dependencies(self, workflow_id: str, step_id: str, dependencies: set[str]) -> Workflow:
        """
        Update the dependency list of a step.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step_id not in wf.steps:
                raise WorkflowNotFoundError(f"Step '{step_id}' not found in workflow '{workflow_id}'.")

            step = wf.steps[step_id]
            updated_step = dataclasses.replace(step, dependencies=frozenset(dependencies))

            new_steps = dict(wf.steps)
            new_steps[step_id] = updated_step

            updated_wf = dataclasses.replace(wf, steps=new_steps)

            validate_workflow(updated_wf)
            self.save_workflow(updated_wf)

            self._event_bus.publish(
                Event(
                    name="WorkflowUpdated",
                    source="workflow.manager",
                    task_id=wf.parent_task_id,
                    payload={"workflow_id": workflow_id},
                )
            )
            return self._cache[workflow_id]

    def update_step_status(
        self,
        workflow_id: str,
        step_id: str,
        new_status: StepState,
        output_data: dict[str, Any] | None = None,
    ) -> Workflow:
        """
        Update the status and outputs of a specific workflow step.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            if step_id not in wf.steps:
                raise WorkflowNotFoundError(f"Step '{step_id}' not found in workflow '{workflow_id}'.")

            step = wf.steps[step_id]
            validate_step_transition(step.status, new_status)

            updated_step = dataclasses.replace(
                step,
                status=new_status,
                output_data=output_data if output_data is not None else step.output_data,
            )

            new_steps = dict(wf.steps)
            new_steps[step_id] = updated_step

            updated_wf = dataclasses.replace(wf, steps=new_steps)

            # Check if workflow is completed or failed
            updated_wf = self._evaluate_workflow_status(updated_wf)

            self.save_workflow(updated_wf)

            # Emit step events
            if new_status == StepState.COMPLETED:
                self._event_bus.publish(
                    Event(
                        name="StepCompleted",
                        source="workflow.manager",
                        task_id=wf.parent_task_id,
                        payload={"workflow_id": workflow_id, "step_id": step_id},
                    )
                )
            elif new_status == StepState.FAILED:
                self._event_bus.publish(
                    Event(
                        name="StepFailed",
                        source="workflow.manager",
                        task_id=wf.parent_task_id,
                        payload={"workflow_id": workflow_id, "step_id": step_id},
                    )
                )

            return self._cache[workflow_id]

    def _evaluate_workflow_status(self, workflow: Workflow) -> Workflow:
        """Evaluate if overall workflow status should transition based on steps statuses."""
        steps_list = list(workflow.steps.values())
        if not steps_list:
            return workflow

        # If any step is running, status is RUNNING
        # If all steps are completed or skipped, workflow is COMPLETED
        # If any step is failed, workflow is FAILED
        # If any step is cancelled, workflow is CANCELLED
        if any(s.status == StepState.FAILED for s in steps_list):
            return dataclasses.replace(workflow, status=WorkflowStatus.FAILED)
        if any(s.status == StepState.CANCELLED for s in steps_list):
            return dataclasses.replace(workflow, status=WorkflowStatus.CANCELLED)
        if all(s.status in {StepState.COMPLETED, StepState.SKIPPED} for s in steps_list):
            return dataclasses.replace(workflow, status=WorkflowStatus.COMPLETED)
        if any(s.status == StepState.RUNNING for s in steps_list):
            return dataclasses.replace(workflow, status=WorkflowStatus.RUNNING)

        return workflow

    def ready_steps(self, workflow_id: str) -> list[WorkflowStep]:
        """
        Transition PENDING or WAITING steps to READY if all their dependencies
        are COMPLETED or SKIPPED. Returns the list of newly transitioned steps.
        """
        with self._lock:
            wf = self.load_workflow(workflow_id)
            new_ready_steps: list[WorkflowStep] = []
            updated_steps = dict(wf.steps)

            for step_id, step in wf.steps.items():
                if step.status in {StepState.PENDING, StepState.WAITING}:
                    # Check dependencies: all must be in COMPLETED or SKIPPED state
                    deps_satisfied = True
                    for dep_id in step.dependencies:
                        dep_step = wf.steps.get(dep_id)
                        if dep_step is None or dep_step.status not in {StepState.COMPLETED, StepState.SKIPPED}:
                            deps_satisfied = False
                            break

                    if deps_satisfied:
                        # Transition to READY
                        updated_step = dataclasses.replace(step, status=StepState.READY)
                        updated_steps[step_id] = updated_step
                        new_ready_steps.append(updated_step)

            if new_ready_steps:
                updated_wf = dataclasses.replace(wf, steps=updated_steps)
                self.save_workflow(updated_wf)

                # Emit updates
                self._event_bus.publish(
                    Event(
                        name="WorkflowUpdated",
                        source="workflow.manager",
                        task_id=wf.parent_task_id,
                        payload={"workflow_id": workflow_id},
                    )
                )

            return new_ready_steps

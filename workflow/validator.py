"""
Workflow validator validating structure, IDs, and capability requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from workflow.exceptions import WorkflowValidationError
from workflow.graph import DependencyGraph

if TYPE_CHECKING:
    from workflow.workflow import Workflow


def validate_workflow(workflow: Workflow) -> None:
    """
    Validate the workflow graph. Checks for:
        - Circular dependencies
        - Missing dependencies
        - Duplicate or mismatched step/workflow IDs
        - Missing required properties (goal/capability)

    Raises:
        WorkflowValidationError: If any validation rule is violated.
    """
    steps_list = list(workflow.steps.values())

    # 1. Check for mismatched workflow references
    for step in steps_list:
        if step.workflow_id != workflow.workflow_id:
            raise WorkflowValidationError(
                f"Step '{step.step_id}' references workflow ID '{step.workflow_id}', "
                f"but parent workflow ID is '{workflow.workflow_id}'."
            )
        if not step.step_id.strip():
            raise WorkflowValidationError("Step ID cannot be empty.")
        if not step.capability.strip():
            raise WorkflowValidationError(
                f"Step '{step.step_id}' must specify a capability requirement."
            )

    # 2. Check duplicate step IDs
    # Dict keys prevent duplicate keys at runtime, but we verify input integrity
    seen_ids = set()
    for step in steps_list:
        if step.step_id in seen_ids:
            raise WorkflowValidationError(f"Duplicate step ID detected: '{step.step_id}'.")
        seen_ids.add(step.step_id)

    # 3. Graph structural checks (circular and missing dependency checks)
    graph = DependencyGraph(steps_list)
    graph.validate()

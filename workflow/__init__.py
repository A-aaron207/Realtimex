"""
Realtimex Workflow Engine package.

Transforms Tasks into execution graphs (DAGs) of logical Steps, manages
structural dependencies, and enforces state machine transitions.

Components:
    - Workflow: execution graph container.
    - WorkflowStep: representation of a single unit of execution.
    - StepState: step state machine lifecycle enum.
    - DependencyGraph: structural DAG sorting and cycle validation.
    - WorkflowManager: coordinator of step changes and status evaluations.
    - WorkflowPersistence: separate workflow disk storage.
    - WorkflowAPI: API exposing plan queries, ready steps, and statuses.
"""

from workflow.api import WorkflowAPI  # noqa: F401
from workflow.exceptions import (  # noqa: F401
    InvalidStepStateTransitionError,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowPersistenceError,
    WorkflowValidationError,
)
from workflow.graph import DependencyGraph  # noqa: F401
from workflow.manager import WorkflowManager  # noqa: F401
from workflow.persistence import WorkflowPersistence  # noqa: F401
from workflow.planner import RuleBasedWorkflowPlanner, WorkflowPlanner  # noqa: F401
from workflow.step import StepState, WorkflowStep, validate_step_transition  # noqa: F401
from workflow.validator import validate_workflow  # noqa: F401
from workflow.workflow import Workflow, WorkflowStatus  # noqa: F401

"""
Dependency Graph representation and validation for Workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from workflow.exceptions import WorkflowValidationError

if TYPE_CHECKING:
    from workflow.step import WorkflowStep


class DependencyGraph:
    """
    Validates workflow step structures, references, and detects circular dependencies.
    Provides topological sorting to order steps by execution priority.
    """

    def __init__(self, steps: list[WorkflowStep]) -> None:
        """
        Initialize and build the graph.

        Args:
            steps: List of WorkflowStep objects.
        """
        self.steps = {s.step_id: s for s in steps}
        self.adj: dict[str, set[str]] = {s.step_id: set() for s in steps}
        self.in_degree: dict[str, int] = {s.step_id: 0 for s in steps}
        self._build_graph()

    def _build_graph(self) -> None:
        """
        Build adjacency list and compute in-degree.
        Validates missing dependency references and duplicate IDs.
        """
        for step_id, step in self.steps.items():
            for dep in step.dependencies:
                if dep not in self.steps:
                    raise WorkflowValidationError(
                        f"Step '{step_id}' depends on missing step '{dep}'."
                    )
                # Edge exists from dep -> step_id (dep must finish before step_id runs)
                self.adj[dep].add(step_id)
                self.in_degree[step_id] += 1

    def validate(self) -> None:
        """
        Perform complete validation checks (circular dependencies detection).
        """
        # A simple check using topological sort. If we can't sort all nodes, a cycle exists.
        try:
            self.topological_sort()
        except WorkflowValidationError as e:
            raise WorkflowValidationError(f"Dependency validation failed: {e}") from e

    def topological_sort(self) -> list[str]:
        """
        Order the step IDs topologically using Kahn's algorithm.

        Returns:
            A list of step IDs in execution order.

        Raises:
            WorkflowValidationError: If a circular dependency (cycle) is detected.
        """
        # Copy in-degrees to avoid mutating state
        in_degrees = dict(self.in_degree)
        
        # Sources: nodes with no incoming edges (no dependencies)
        queue = [step_id for step_id, degree in in_degrees.items() if degree == 0]
        
        # Sort queue to ensure deterministic ordering (e.g. alphabetically)
        queue.sort()
        
        ordered: list[str] = []

        while queue:
            # We pop the first element
            u = queue.pop(0)
            ordered.append(u)

            # Reduce in-degree of all neighbors
            for neighbor in self.adj[u]:
                in_degrees[neighbor] -= 1
                if in_degrees[neighbor] == 0:
                    queue.append(neighbor)
            
            # Keep queue sorted for deterministic execution
            queue.sort()

        if len(ordered) != len(self.steps):
            cycle_nodes = [node for node, degree in in_degrees.items() if degree > 0]
            raise WorkflowValidationError(
                f"Circular dependency detected containing steps: {cycle_nodes}"
            )

        return ordered

"""
Goal Graph decomposition module for Planner 2.0.

Decomposes high-level task objectives into a dependency graph (DAG) of explicit sub-goals
before step formulation and execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from cognitive.exceptions import ValidationError

GoalStatus = Literal["PENDING", "RESOLVED", "FAILED", "BLOCKED"]


@dataclass
class GoalNode:
    """
    Represents a single sub-goal node within a GoalGraph.
    """
    goal_id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    produced_outputs: list[str] = field(default_factory=list)
    capability: str | None = None
    status: GoalStatus = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "dependencies": self.dependencies,
            "required_inputs": self.required_inputs,
            "produced_outputs": self.produced_outputs,
            "capability": self.capability,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalNode:
        return cls(
            goal_id=data["goal_id"],
            description=data["description"],
            dependencies=data.get("dependencies", []),
            required_inputs=data.get("required_inputs", []),
            produced_outputs=data.get("produced_outputs", []),
            capability=data.get("capability"),
            status=data.get("status", "PENDING"),
            metadata=data.get("metadata", {}),
        )


class GoalGraph:
    """
    Dependency graph of sub-goals representing a decomposed task objective.
    """

    def __init__(self, objective: str = "") -> None:
        self.objective = objective
        self.nodes: dict[str, GoalNode] = {}

    def add_node(self, node: GoalNode) -> None:
        """Add a sub-goal node to the graph."""
        if node.goal_id in self.nodes:
            raise ValidationError(f"Duplicate goal_id '{node.goal_id}' in GoalGraph.")
        self.nodes[node.goal_id] = node

    def get_node(self, goal_id: str) -> GoalNode | None:
        """Retrieve node by ID."""
        return self.nodes.get(goal_id)

    def validate_dag(self) -> bool:
        """
        Verify all dependencies exist and check for cycles in the graph.
        """
        for gid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise ValidationError(
                        f"Goal '{gid}' depends on non-existent goal '{dep}'."
                    )

        visited: dict[str, int] = {gid: 0 for gid in self.nodes}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(curr: str) -> bool:
            visited[curr] = 1
            for neighbor in self.nodes[curr].dependencies:
                if visited[neighbor] == 1:
                    return True  # Cycle found
                if visited[neighbor] == 0:
                    if dfs(neighbor):
                        return True
            visited[curr] = 2
            return False

        for gid in self.nodes:
            if visited[gid] == 0:
                if dfs(gid):
                    raise ValidationError("Circular dependency detected in GoalGraph.")

        return True

    def get_executable_nodes(self) -> list[GoalNode]:
        """
        Return nodes whose status is PENDING and all dependencies are RESOLVED.
        """
        executable: list[GoalNode] = []
        for node in self.nodes.values():
            if node.status != "PENDING":
                continue
            deps_resolved = all(
                self.nodes[dep].status == "RESOLVED"
                for dep in node.dependencies
                if dep in self.nodes
            )
            if deps_resolved:
                executable.append(node)
        return executable

    def topological_sort(self) -> list[GoalNode]:
        """
        Return nodes in topological dependency execution order.
        """
        self.validate_dag()
        visited: set[str] = set()
        order: list[GoalNode] = []

        def visit(gid: str) -> None:
            if gid not in visited:
                visited.add(gid)
                for dep in self.nodes[gid].dependencies:
                    visit(dep)
                order.append(self.nodes[gid])

        for gid in self.nodes:
            visit(gid)

        return order

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "nodes": [n.to_dict() for n in self.nodes.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalGraph:
        graph = cls(objective=data.get("objective", ""))
        for n_dict in data.get("nodes", []):
            graph.add_node(GoalNode.from_dict(n_dict))
        graph.validate_dag()
        return graph

    @classmethod
    def decompose_objective(cls, objective: str, capability_hints: list[str] | None = None) -> GoalGraph:
        """
        Decompose a high-level user objective into a structured GoalGraph.
        Pre-forms common sub-goals (need input -> need resolution -> need action -> need output).
        """
        graph = cls(objective=objective)
        obj_lower = objective.lower()

        # Heuristic decomposition based on objective intent
        if "file" in obj_lower or "write" in obj_lower or "save" in obj_lower or "create" in obj_lower:
            graph.add_node(GoalNode(
                goal_id="g1_resolve_path",
                description="Determine file destination path and name",
                produced_outputs=["destination_path", "filename"],
            ))
            graph.add_node(GoalNode(
                goal_id="g2_prepare_content",
                description="Generate or prepare file content",
                produced_outputs=["file_content"],
            ))
            graph.add_node(GoalNode(
                goal_id="g3_execute_write",
                description="Write content to target file path",
                dependencies=["g1_resolve_path", "g2_prepare_content"],
                required_inputs=["destination_path", "file_content"],
                capability="write_file",
            ))
        elif "search" in obj_lower or "research" in obj_lower or "find" in obj_lower:
            graph.add_node(GoalNode(
                goal_id="g1_query_formulation",
                description="Formulate target search query keywords",
                produced_outputs=["search_query"],
            ))
            graph.add_node(GoalNode(
                goal_id="g2_execute_search",
                description="Execute search query across web/workspace",
                dependencies=["g1_query_formulation"],
                required_inputs=["search_query"],
                capability="search",
            ))
            graph.add_node(GoalNode(
                goal_id="g3_synthesize_results",
                description="Summarize and synthesize retrieved search findings",
                dependencies=["g2_execute_search"],
                required_inputs=["search_results"],
            ))
        else:
            # Default single-goal graph fallback
            graph.add_node(GoalNode(
                goal_id="g1_execute_objective",
                description=objective,
            ))

        graph.validate_dag()
        return graph

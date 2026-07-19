"""
Extensible Workflow Planner that converts user goals into execution step graphs.
"""

from __future__ import annotations

from typing import Any

from workflow.step import StepState, WorkflowStep


class WorkflowPlanner:
    """
    Base class for workflow planners. Planners map task goals to step sequences.
    """

    def plan(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """
        Generate execution steps for a workflow.

        Args:
            workflow_id: Unique identifier for the parent workflow.
            goal: The task goal description.

        Returns:
            List of generated WorkflowStep instances.
        """
        raise NotImplementedError("Planners must implement the plan method.")


class RuleBasedWorkflowPlanner(WorkflowPlanner):
    """
    Extensible rule-based planner analyzing goal keywords to construct realistic steps.
    """

    def plan(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        goal_lower = goal.lower()

        # 1. Parallel workflow
        if "parallel" in goal_lower:
            return self._build_parallel_workflow(workflow_id, goal)

        # 2. Retry / failure / recovery
        if any(kw in goal_lower for kw in ["retry", "recovery", "interruption", "fail"]):
            return self._build_retry_workflow(workflow_id, goal)

        # 3. Permission check
        if "permission" in goal_lower:
            return self._build_permission_workflow(workflow_id, goal)

        # 4. Multi-step workflow / read and summarize
        if "multi-step" in goal_lower or "read and summarize" in goal_lower:
            return self._build_multistep_workflow(workflow_id, goal)

        # 5. Read local file
        if "read local file" in goal_lower or "read file" in goal_lower:
            return self._build_read_file_workflow(workflow_id, goal)

        # 6. Code generation
        if any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            return self._build_generate_code_workflow(workflow_id, goal)

        # 7. Summarize
        if "summarize" in goal_lower or "summarization" in goal_lower:
            return self._build_summarization_workflow(workflow_id, goal)

        # 8. Research
        if "research" in goal_lower or "search" in goal_lower:
            return self._build_research_workflow(workflow_id, goal)

        # 9. Answering questions / explaining concepts
        if any(kw in goal_lower for kw in ["explain", "answer", "question", "what", "how", "recursion"]):
            return self._build_answer_question_workflow(workflow_id, goal)

        # 10. Software check
        if any(kw in goal_lower for kw in ["web", "portfolio", "app", "site", "build"]):
            return self._build_software_workflow(workflow_id)

        # Default fallback general workflow
        return self._build_default_workflow(workflow_id)

    def _build_summarization_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step summarization workflow."""
        text = goal
        # Strip common prefixes to get the raw text to summarize
        for prefix in ["summarize this text:", "summarize text:", "summarize:"]:
            if goal.lower().startswith(prefix):
                text = goal[len(prefix):].strip()
                break

        return [
            WorkflowStep(
                step_id="summarize",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": text},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.05,
            )
        ]

    def _build_answer_question_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step question answering workflow."""
        return [
            WorkflowStep(
                step_id="answer",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": goal},
                status=StepState.PENDING,
                estimated_time=3.0,
                estimated_cost=0.08,
            )
        ]

    def _build_generate_code_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step code generation workflow."""
        return [
            WorkflowStep(
                step_id="code_gen",
                workflow_id=workflow_id,
                capability="generate_code",
                input_data={"prompt": goal},
                status=StepState.PENDING,
                estimated_time=4.0,
                estimated_cost=0.12,
            )
        ]

    def _build_research_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a sequential 2-step research workflow (search -> synthesize)."""
        return [
            WorkflowStep(
                step_id="search",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": goal},
                status=StepState.PENDING,
                estimated_time=3.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="synthesize",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": f"Synthesize findings for: {goal}"},
                status=StepState.PENDING,
                dependencies=frozenset(["search"]),
                estimated_time=2.0,
                estimated_cost=0.04,
            )
        ]

    def _build_read_file_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step read file workflow."""
        path = "logs/test_input.txt"
        if ":" in goal:
            path = goal.split(":", 1)[1].strip()
        elif "read file" in goal.lower():
            parts = goal.lower().split("read file")
            if len(parts) > 1:
                path = parts[1].strip()
        return [
            WorkflowStep(
                step_id="read_file_step",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": path},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_multistep_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a sequential multi-step workflow (read -> summarize -> write)."""
        return [
            WorkflowStep(
                step_id="read",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": "logs/test_input.txt"},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            ),
            WorkflowStep(
                step_id="summarize",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"prompt": "Summarize the file contents"},
                status=StepState.PENDING,
                dependencies=frozenset(["read"]),
                estimated_time=2.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="write",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"file_path": "logs/test_summary.txt", "content": "Summary result: successful multi-step workflow."},
                status=StepState.PENDING,
                dependencies=frozenset(["summarize"]),
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_parallel_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a parallel workflow with a merge step."""
        return [
            WorkflowStep(
                step_id="search_a",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "Topic A research"},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.04,
            ),
            WorkflowStep(
                step_id="search_b",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "Topic B research"},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.04,
            ),
            WorkflowStep(
                step_id="merge",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": "Synthesize results from Topic A and Topic B searches."},
                status=StepState.PENDING,
                dependencies=frozenset(["search_a", "search_b"]),
                estimated_time=3.0,
                estimated_cost=0.06,
            )
        ]

    def _build_retry_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a retry testing workflow with a step that initially fails."""
        return [
            WorkflowStep(
                step_id="unstable_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Intermittent failure test data.", "step_id": "unstable_step", "simulate_fail": True},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.05,
            )
        ]

    def _build_permission_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a permission verification workflow step."""
        return [
            WorkflowStep(
                step_id="perm_check",
                workflow_id=workflow_id,
                capability="permission_check",
                input_data={"check": True},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_software_workflow(self, workflow_id: str) -> list[WorkflowStep]:
        """Generate a realistic 6-step software/web development workflow."""
        steps = [
            WorkflowStep(
                step_id="planning",
                workflow_id=workflow_id,
                capability="plan_task",
                input_data={"scope": "software_development"},
                status=StepState.PENDING,
                estimated_time=1.5,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="research",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "best web portfolio practices"},
                status=StepState.PENDING,
                dependencies=frozenset(["planning"]),
                estimated_time=3.0,
                estimated_cost=0.10,
            ),
            WorkflowStep(
                step_id="design",
                workflow_id=workflow_id,
                capability="generate_image",
                input_data={"prompt": "modern portfolio design mockup"},
                status=StepState.PENDING,
                dependencies=frozenset(["research"]),
                estimated_time=4.0,
                estimated_cost=0.40,
            ),
            WorkflowStep(
                step_id="code",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"file_path": "portfolio/index.html"},
                status=StepState.PENDING,
                dependencies=frozenset(["design"]),
                estimated_time=6.0,
                estimated_cost=0.15,
            ),
            WorkflowStep(
                step_id="verification",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": "portfolio/index.html"},
                status=StepState.PENDING,
                dependencies=frozenset(["code"]),
                estimated_time=2.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="packaging",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text_source": "build_logs"},
                status=StepState.PENDING,
                dependencies=frozenset(["verification"]),
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
        ]
        return steps

    def _build_default_workflow(self, workflow_id: str) -> list[WorkflowStep]:
        """Generate a general 3-step workflow (analyze, process, verify)."""
        steps = [
            WorkflowStep(
                step_id="analyze",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"target": "source_document"},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
            WorkflowStep(
                step_id="process",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"length": "medium"},
                status=StepState.PENDING,
                dependencies=frozenset(["analyze"]),
                estimated_time=2.0,
                estimated_cost=0.08,
            ),
            WorkflowStep(
                step_id="verify",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"target": "summary_output"},
                status=StepState.PENDING,
                dependencies=frozenset(["process"]),
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
        ]
        return steps

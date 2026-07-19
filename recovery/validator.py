"""
State Validator implementation for verifying recovered structures in Realtimex.
"""

from __future__ import annotations

from typing import Any


class StateValidator:
    """
    Validates structural schemas and references for recovered states (Tasks, Workflows, Memory).
    Enforces isolation of invalid states to prevent recovery failures from halting kernel boots.
    
    Validation philosophy:
    - Never crash the recovery process due to schema issues
    - Isolate corrupted items for user review
    - Provide detailed diagnostics in warnings
    - Allow system to boot with best-effort state restoration
    """

    def validate_task(self, task: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Verify task schema keys and structure.
        
        Required fields: task_id, status, action
        Valid statuses: created, active, completed, failed, pending, running, paused, cancelled
        
        Args:
            task: Task dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required fields
        required = {"task_id", "status", "action"}
        missing = required - set(task.keys())
        if missing:
            return False, f"Task schema is missing required fields: {missing}"
        
        # Validate task_id is non-empty string
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return False, f"Task 'task_id' must be a non-empty string, got: {type(task_id).__name__}"
        
        # Validate status field
        status = task.get("status")
        valid_statuses = {"created", "active", "completed", "failed", "pending", "running", "paused", "cancelled"}
        if status not in valid_statuses:
            return False, f"Task '{task_id}' has invalid status '{status}'. Valid statuses: {valid_statuses}"
        
        # Validate action is non-empty string
        action = task.get("action")
        if not isinstance(action, str) or not action.strip():
            return False, f"Task '{task_id}' has invalid action: {type(action).__name__}"
            
        return True, None

    def validate_workflow(self, workflow: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Verify workflow schema keys and structure.
        
        Required fields: workflow_id, status, steps
        Valid statuses: created, active, completed, failed, pending, paused
        
        Args:
            workflow: Workflow dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required fields
        required = {"workflow_id", "status", "steps"}
        missing = required - set(workflow.keys())
        if missing:
            return False, f"Workflow schema is missing required fields: {missing}"
        
        # Validate workflow_id is non-empty string
        workflow_id = workflow.get("workflow_id")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            return False, f"Workflow 'workflow_id' must be a non-empty string, got: {type(workflow_id).__name__}"
        
        # Validate status field
        status = workflow.get("status")
        valid_statuses = {"created", "active", "completed", "failed", "pending", "paused"}
        if status not in valid_statuses:
            return False, f"Workflow '{workflow_id}' has invalid status '{status}'. Valid statuses: {valid_statuses}"
        
        # Validate steps is dict or list
        steps = workflow.get("steps")
        if not isinstance(steps, (dict, list)):
            return False, f"Workflow '{workflow_id}' steps must be a dictionary or a list, got: {type(steps).__name__}"
            
        return True, None

    def validate_memory_reference(self, mem_ref: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Verify memory reference layout and structure.
        
        Required fields: memory_id, scope
        Valid scopes: global, session, task, workflow
        
        Args:
            mem_ref: Memory reference dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required fields
        required = {"memory_id", "scope"}
        missing = required - set(mem_ref.keys())
        if missing:
            return False, f"Memory reference schema is missing required fields: {missing}"
        
        # Validate memory_id is non-empty string
        memory_id = mem_ref.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id.strip():
            return False, f"Memory 'memory_id' must be a non-empty string, got: {type(memory_id).__name__}"
        
        # Validate scope is valid
        scope = mem_ref.get("scope")
        valid_scopes = {"global", "session", "task", "workflow"}
        if scope not in valid_scopes:
            return False, f"Memory reference '{memory_id}' has invalid scope '{scope}'. Valid scopes: {valid_scopes}"
            
        return True, None

    def validate_checkpoint_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate all data elements in a checkpoint.
        
        Isolates corrupted or invalid elements to a separate metadata partition
        rather than raising exceptions or failing the checkpoint evaluation.
        
        Strategy:
        1. Iterate through all tasks, workflows, and memories
        2. Validate each using schema rules
        3. Separate valid items to 'clean' and invalid to 'isolated'
        4. Log warnings for each isolated item
        5. Return comprehensive validation outcome
        
        Args:
            data: Checkpoint data dictionary to validate
            
        Returns:
            dict with keys:
                - clean: Valid data organized by type (tasks, workflows, memories, kernel_metadata, pending_events)
                - isolated: Invalid data organized by type (tasks, workflows, memories)
                - warnings: List of validation issue descriptions
        """
        clean_tasks: list[dict[str, Any]] = []
        clean_workflows: list[dict[str, Any]] = []
        clean_memories: list[dict[str, Any]] = []
        
        isolated_tasks: list[dict[str, Any]] = []
        isolated_workflows: list[dict[str, Any]] = []
        isolated_memories: list[dict[str, Any]] = []
        
        warnings: list[str] = []

        # 1. Validate Tasks
        for t in data.get("tasks", []):
            is_valid, err = self.validate_task(t)
            if is_valid:
                clean_tasks.append(t)
            else:
                isolated_tasks.append(t)
                warnings.append(f"Task Isolation Warning: {err}")

        # 2. Validate Workflows
        for w in data.get("workflows", []):
            is_valid, err = self.validate_workflow(w)
            if is_valid:
                clean_workflows.append(w)
            else:
                isolated_workflows.append(w)
                warnings.append(f"Workflow Isolation Warning: {err}")

        # 3. Validate Memory References
        for m in data.get("memories", []):
            is_valid, err = self.validate_memory_reference(m)
            if is_valid:
                clean_memories.append(m)
            else:
                isolated_memories.append(m)
                warnings.append(f"Memory Isolation Warning: {err}")

        return {
            "clean": {
                "tasks": clean_tasks,
                "workflows": clean_workflows,
                "memories": clean_memories,
                "kernel_metadata": data.get("kernel_metadata", {}),
                "pending_events": data.get("pending_events", []),
            },
            "isolated": {
                "tasks": isolated_tasks,
                "workflows": isolated_workflows,
                "memories": isolated_memories,
            },
            "warnings": warnings,
        }

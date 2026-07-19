"""
Recovery Planner implementation for charting state restoration steps in Realtimex.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from recovery.exceptions import RecoveryPlannerError
from recovery.policies import RecoveryPolicy
from recovery.validator import StateValidator


@dataclass
class RecoveryPlan:
    """
    Representation of a charted recovery sequence.
    
    Attributes:
        checkpoint_id: ID of the checkpoint being recovered
        steps: Ordered list of recovery steps to execute
        clean_data: Validated data that passed schema checks
        isolated_data: Data that failed validation
        warnings: List of validation or planning issues
        errors: List of critical planning errors
    """
    checkpoint_id: str
    steps: list[str] = field(default_factory=list)
    clean_data: dict[str, Any] = field(default_factory=dict)
    isolated_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RecoveryPlanner:
    """
    Determines and schedules recovery sequences, checking compatibility
    and enforcing strict or fail-safe policies on corrupted datasets.
    
    Recovery Planning Strategy:
    1. Validate all checkpoint data using StateValidator
    2. Separate valid (clean) and invalid (isolated) data
    3. Check recovery strategy (strict vs fail_safe)
    4. Chart recovery steps based on what needs to be restored
    5. Return a RecoveryPlan with execution instructions
    
    Strict Strategy:
    - If ANY corruption is detected, abort recovery completely
    - Used for production environments where data integrity is paramount
    
    Fail-Safe Strategy:
    - Recover all valid data, isolate corrupted items
    - Continue recovery despite corruption
    - Used for resilient systems that prioritize availability
    """

    def __init__(
        self,
        validator: StateValidator,
        policy: RecoveryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.validator = validator
        self.policy = policy or RecoveryPolicy()
        self.logger = logger or logging.getLogger("realtimex.recovery.planner")

    def plan_recovery(self, checkpoint_id: str, checkpoint_data: dict[str, Any]) -> RecoveryPlan:
        """
        Validate checkpoint contents and chart chronological recovery actions.
        
        Planning Sequence:
        1. Run Validation & Isolation on all checkpoint data
        2. Check recovery strategy and apply policy rules
        3. Chart ordered recovery steps
        4. Return plan with clean data, isolated items, and action sequence
        
        Args:
            checkpoint_id: ID of checkpoint to plan recovery for
            checkpoint_data: Raw checkpoint data dictionary
            
        Returns:
            RecoveryPlan: Detailed plan with steps and data
            
        Raises:
            RecoveryPlannerError: If strategy is strict and corruption detected
        """
        self.logger.info("Planning recovery for checkpoint: %s", checkpoint_id)
        
        # 1. Run Validation & Isolation
        validation_outcome = self.validator.validate_checkpoint_data(checkpoint_data)
        
        warnings = validation_outcome["warnings"]
        clean = validation_outcome["clean"]
        isolated = validation_outcome["isolated"]
        
        errors: list[str] = []

        # 2. Enforce Strategy Policies
        if self.policy.recovery_strategy == "strict" and warnings:
            # Under strict strategy, any schema isolation triggers recovery abort
            msg = (
                f"Recovery aborted: Corrupted data detected under Strict strategy. "
                f"Isolation count: {len(isolated.get('tasks', [])) + len(isolated.get('workflows', [])) + len(isolated.get('memories', []))}. "
                f"Details: {warnings[0]}"
            )
            self.logger.error("Recovery planning failed: %s", msg)
            raise RecoveryPlannerError(msg)

        # Log planning details
        if isolated.get("tasks"):
            self.logger.warning("Recovery plan: %d tasks isolated", len(isolated["tasks"]))
        if isolated.get("workflows"):
            self.logger.warning("Recovery plan: %d workflows isolated", len(isolated["workflows"]))

        # 3. Chart Steps based on what needs restoration
        steps = ["validate_checkpoint"]
        
        if clean.get("tasks"):
            steps.append("restore_tasks")
            self.logger.debug("Recovery plan includes: restore %d tasks", len(clean["tasks"]))
            
        if clean.get("workflows"):
            steps.append("restore_workflows")
            self.logger.debug("Recovery plan includes: restore %d workflows", len(clean["workflows"]))
            
        if clean.get("memories"):
            steps.append("restore_memories")
            self.logger.debug("Recovery plan includes: restore %d memory references", len(clean["memories"]))
            
        if clean.get("pending_events"):
            steps.append("restore_pending_events")
            self.logger.debug("Recovery plan includes: %d pending events", len(clean["pending_events"]))
            
        steps.append("generate_recovery_report")

        plan = RecoveryPlan(
            checkpoint_id=checkpoint_id,
            steps=steps,
            clean_data=clean,
            isolated_data=isolated,
            warnings=warnings,
            errors=errors,
        )
        
        self.logger.info("Recovery plan complete: %d steps, %d warnings", len(steps), len(warnings))
        return plan

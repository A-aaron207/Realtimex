"""
Agent Execution Engine (Executor 2.0) for Realtimex.

Orchestrates the full action execution reliability loop:
Pre-check -> Execute -> Observe -> Validate -> Repair -> Retry -> Return
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from cognitive.action_validator import ActionValidator, ValidationResult
from execution.observer import ExecutionObservation, ExecutionObserver
from execution.repair import ExecutionRepairEngine, RepairResult
from execution.validator import ExecutionResultValidator, ExecutionValidationResult


@dataclass
class ExecutionEngineReport:
    """
    Comprehensive report returned by AgentExecutionEngine after executing a step.
    """
    step_id: str
    capability: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1
    repaired: bool = False
    repair_summary: str | None = None
    observation: ExecutionObservation | None = None
    validation: ExecutionValidationResult | None = None
    execution_time_total_ms: float = 0.0
    error: str | None = None


class AgentExecutionEngine:
    """
    Executor 2.0 kernel execution orchestrator.
    Drives pre-check validation, execution, observation, result validation,
    deterministic local repair, and retries.
    """

    def __init__(
        self,
        max_retries: int = 3,
        min_confidence_threshold: float = 0.70,
        fallback_dir: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.action_validator = ActionValidator(min_confidence_threshold=min_confidence_threshold)
        self.observer = ExecutionObserver()
        self.result_validator = ExecutionResultValidator()
        self.repair_engine = ExecutionRepairEngine(logger=logger)
        self.fallback_dir = fallback_dir
        self.logger = logger or logging.getLogger("realtimex.execution")

    def execute_step(
        self,
        step: dict[str, Any],
        worker_executor: Callable[[dict[str, Any]], dict[str, Any]],
        context: dict[str, Any] | None = None,
        available_capabilities: list[str] | None = None,
        granted_permissions: set[str] | None = None,
        confidence_score: float = 1.0,
    ) -> ExecutionEngineReport:
        """
        Execute an action step through the complete Executor 2.0 Reliability Loop.

        Loop steps:
        1. Pre-check (ActionValidator)
        2. Execute (Worker)
        3. Observe (Observer)
        4. Validate (Result Validator)
        5. Repair (Local Repair Engine)
        6. Retry (if needed up to max_retries)
        7. Return (Validated ExecutionEngineReport)
        """
        step_id = step.get("step_id", "unknown_step")
        capability = step.get("capability", "unknown_capability")
        input_data = dict(step.get("input_data") or step.get("input") or {})

        start_time_total = time.perf_counter()

        # 1. Pre-check validation
        pre_check = self.action_validator.validate_action(
            step=step,
            context=context,
            available_capabilities=available_capabilities,
            granted_permissions=granted_permissions,
            confidence_score=confidence_score,
        )

        if not pre_check.is_valid:
            self.logger.warning("Pre-check failed for step '%s': %s", step_id, pre_check.reason)
            return ExecutionEngineReport(
                step_id=step_id,
                capability=capability,
                status="FAILED",
                error=f"Pre-check failed: {pre_check.reason}",
                execution_time_total_ms=(time.perf_counter() - start_time_total) * 1000,
            )

        attempts = 0
        repaired_ever = False
        repair_summary: str | None = None
        current_input = dict(input_data)
        last_obs: ExecutionObservation | None = None
        last_val: ExecutionValidationResult | None = None

        while attempts < self.max_retries:
            attempts += 1
            start_attempt_time = time.perf_counter()
            raw_result: dict[str, Any] | None = None
            exec_exception: Exception | None = None

            # 2. Execute step
            try:
                raw_result = worker_executor(current_input)
            except Exception as e:
                exec_exception = e
                self.logger.warning("Execution exception on step '%s' attempt %d: %s", step_id, attempts, e)

            attempt_duration_ms = (time.perf_counter() - start_attempt_time) * 1000

            # 3. Observe result
            last_obs = self.observer.observe(
                step_id=step_id,
                capability=capability,
                raw_result=raw_result,
                exception=exec_exception,
                duration_ms=attempt_duration_ms,
            )

            # 4. Validate result
            last_val = self.result_validator.validate_observation(last_obs, current_input)

            if last_val.is_valid:
                # Execution succeeded and passed post-conditions!
                total_duration = (time.perf_counter() - start_time_total) * 1000
                return ExecutionEngineReport(
                    step_id=step_id,
                    capability=capability,
                    status="SUCCESS",
                    output=last_obs.output,
                    attempts=attempts,
                    repaired=repaired_ever,
                    repair_summary=repair_summary,
                    observation=last_obs,
                    validation=last_val,
                    execution_time_total_ms=total_duration,
                )

            # 5. Repair if validation failed and repair is recommended
            if last_val.requires_repair and last_val.repair_strategy and attempts < self.max_retries:
                repair_res = self.repair_engine.attempt_repair(
                    strategy=last_val.repair_strategy,
                    capability=capability,
                    input_data=current_input,
                    error_msg=last_val.reason,
                    fallback_dir=self.fallback_dir,
                )

                if repair_res.success:
                    repaired_ever = True
                    repair_summary = repair_res.message
                    current_input = repair_res.repaired_input
                    self.logger.info("Step '%s' repaired via strategy '%s'. Retrying attempt %d...", step_id, repair_res.strategy_used, attempts + 1)
                    continue

        # Exhausted retries
        total_duration = (time.perf_counter() - start_time_total) * 1000
        return ExecutionEngineReport(
            step_id=step_id,
            capability=capability,
            status="FAILED",
            output=last_obs.output if last_obs else {},
            attempts=attempts,
            repaired=repaired_ever,
            repair_summary=repair_summary,
            observation=last_obs,
            validation=last_val,
            execution_time_total_ms=total_duration,
            error=last_val.reason if last_val else (last_obs.error if last_obs else "Execution failed"),
        )

"""
Reasoning representations and providers for the Realtimex Cognitive Engine.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class CognitiveRequest:
    """
    Structured representation of a cognitive reasoning request.
    """
    task_id: str
    objective: str
    workflow_id: str | None = None
    current_context: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    available_capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "objective": self.objective,
            "current_context": self.current_context,
            "constraints": self.constraints,
            "available_capabilities": self.available_capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveRequest:
        return cls(
            task_id=data["task_id"],
            workflow_id=data.get("workflow_id"),
            objective=data["objective"],
            current_context=data.get("current_context", {}),
            constraints=data.get("constraints", []),
            available_capabilities=data.get("available_capabilities", []),
        )


@dataclass(frozen=True)
class CognitiveResponse:
    """
    Structured response returning recommendations, reasoning, and metadata.
    """
    recommendation: Any
    confidence: float
    reasoning_summary: str
    risks: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence score must be between 0.0 and 1.0. Got: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning_summary": self.reasoning_summary,
            "risks": self.risks,
            "suggested_actions": self.suggested_actions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveResponse:
        return cls(
            recommendation=data["recommendation"],
            confidence=float(data["confidence"]),
            reasoning_summary=data["reasoning_summary"],
            risks=data.get("risks", []),
            suggested_actions=data.get("suggested_actions", []),
            metadata=data.get("metadata", {}),
        )


class ReasoningProvider(ABC):
    """
    Abstract interface for a reasoning provider.
    Allows the Cognitive Engine to be model/provider-agnostic.
    """

    @abstractmethod
    def reason(
        self,
        request: CognitiveRequest,
        context: dict[str, Any],
        decision_type: str,
    ) -> dict[str, Any]:
        """
        Ask the reasoning provider to evaluate the request under the collected context.

        Args:
            request: The cognitive reasoning request.
            context: Collected contextual information.
            decision_type: The type/category of decision being made.

        Returns:
            A dictionary containing the parsed reasoning outcome with fields:
            - recommendation
            - confidence (float)
            - reasoning_summary (str)
            - risks (list[str])
            - suggested_actions (list[str])
            - metadata (dict)
        """
        pass


class MockReasoningProvider(ReasoningProvider):
    """
    Rule-based, extensible mock reasoning provider for local testing and configuration
    without hitting live model endpoints.
    """

    def reason(
        self,
        request: CognitiveRequest,
        context: dict[str, Any],
        decision_type: str,
    ) -> dict[str, Any]:
        decision_type_lower = decision_type.lower()
        objective_lower = request.objective.lower()

        # Default fallback values
        recommendation: Any = "Proceed with execution."
        confidence = 0.90
        reasoning_summary = f"Mock evaluation for {decision_type} complete."
        risks: list[str] = []
        suggested_actions: list[str] = []
        metadata: dict[str, Any] = {"mock_timestamp": datetime.now(timezone.utc).isoformat()}

        if "workflow planning" in decision_type_lower:
            # Recommending step sequences
            if "web" in objective_lower or "portfolio" in objective_lower or "app" in objective_lower:
                recommendation = {
                    "steps": [
                        {
                            "step_id": "fetch_tokens",
                            "capability": "read_file",
                            "input_data": {"file_path": "config/secrets.json"},
                            "dependencies": [],
                        },
                        {
                            "step_id": "deploy_static",
                            "capability": "write_file",
                            "input_data": {"file_path": "dist/index.html"},
                            "dependencies": ["fetch_tokens"],
                        }
                    ]
                }
                reasoning_summary = "Structured software deployment workflow planned."
                suggested_actions = ["Validate file presence in dist/ before writing."]
            else:
                recommendation = {
                    "steps": [
                        {
                            "step_id": "analyze",
                            "capability": "read_file",
                            "input_data": {"target": "source_document"},
                            "dependencies": [],
                        },
                        {
                            "step_id": "process",
                            "capability": "summarize_text",
                            "input_data": {"length": "medium"},
                            "dependencies": ["analyze"],
                        }
                    ]
                }
                reasoning_summary = "Default workflow steps recommended."
        
        elif "permission review" in decision_type_lower:
            # Verify if constraints or sandbox requirements are violated
            required_permissions = request.current_context.get("required_permissions", [])
            declared_permissions = context.get("permissions", {})
            
            unsafe = False
            for perm in required_permissions:
                if perm == "terminal" and not declared_permissions.get("terminal", False):
                    unsafe = True
                    risks.append("Task requests terminal execution but module manifest disables terminal sandbox permission.")
            
            if unsafe:
                recommendation = "Reject execution permission request."
                confidence = 0.95
                reasoning_summary = "Security risk: requested operations violate module sandbox permissions."
                suggested_actions = ["Request terminal sandbox permission elevation or modify the step implementation."]
            else:
                recommendation = "Approve execution permissions."
                confidence = 0.92
                reasoning_summary = "Sandbox checks passed. Necessary permissions are declared."
                suggested_actions = ["Execute step in sandboxed worker."]
                
        elif "risk analysis" in decision_type_lower:
            # Risk estimation based on objective and constraints
            for constraint in request.constraints:
                if "timeout" in constraint.lower() or "limit" in constraint.lower():
                    risks.append(f"Constraint '{constraint}' poses scheduling latency risk under high load.")
            
            if not request.constraints:
                risks.append("No task constraints defined, potential infinite loop risk.")
                suggested_actions.append("Add timeout constraint to the task.")
                
            recommendation = {"risk_level": "medium" if risks else "low"}
            confidence = 0.88
            reasoning_summary = f"Risk analysis generated based on {len(request.constraints)} constraints."
            
        elif "conflict resolution" in decision_type_lower:
            # Check for concurrent conflicts
            steps = context.get("workflow", {}).get("steps", {})
            write_steps = [s_id for s_id, s in steps.items() if s.get("capability") == "write_file"]
            
            if len(write_steps) > 1:
                risks.append(f"Concurrent file writes detected across step: {', '.join(write_steps)}")
                recommendation = {
                    "resolution": "Enforce sequential dependencies between conflicting file write steps.",
                    "sequential_order": write_steps
                }
                suggested_actions.append(f"Link {write_steps[1]} to depend on {write_steps[0]}.")
                reasoning_summary = "Write conflict resolved by ordering steps sequentially."
                confidence = 0.90
            else:
                recommendation = {"resolution": "No conflicts detected. Proceed in parallel."}
                confidence = 0.95
                reasoning_summary = "Workflow concurrency checks passed successfully."
                
        elif "capability selection" in decision_type_lower:
            # Select best capability provider
            objective_cap = request.objective.strip()
            available = request.available_capabilities or context.get("available_capabilities", [])
            
            if objective_cap in available:
                recommendation = {"selected_capability": objective_cap, "confidence": 1.0}
                confidence = 0.99
                reasoning_summary = f"Exact capability match '{objective_cap}' found."
            else:
                # Find partial match
                match = None
                for cap in available:
                    if objective_cap.lower() in cap.lower() or cap.lower() in objective_cap.lower():
                        match = cap
                        break
                if match:
                    recommendation = {"selected_capability": match, "confidence": 0.8}
                    confidence = 0.85
                    reasoning_summary = f"Partial match found: selected capability '{match}' for objective '{objective_cap}'."
                else:
                    recommendation = {"selected_capability": None}
                    confidence = 0.50
                    reasoning_summary = f"No suitable capability provider found for objective '{objective_cap}'."
                    risks.append(f"Missing provider for capability: '{objective_cap}'")
                    suggested_actions.append("Register a new module providing this capability.")

        elif "recovery recommendation" in decision_type_lower:
            # Suggest a recovery action for task failure
            failed_reason = context.get("task", {}).get("metadata", {}).get("failure_reason", "unknown")
            if "timeout" in failed_reason.lower():
                recommendation = {"action": "retry_with_backoff", "multiplier": 2.0}
                suggested_actions.append("Retry step with increased estimated_time constraint.")
                reasoning_summary = "Timeout recovery: retry with exponential delay."
            elif "permission" in failed_reason.lower():
                recommendation = {"action": "fail_fast"}
                suggested_actions.append("Notify admin of permission policy violation.")
                reasoning_summary = "Security failure: do not auto-retry."
            else:
                recommendation = {"action": "retry_immediate"}
                suggested_actions.append("Retry step.")
                reasoning_summary = "Unrecognized failure: default to immediate retry."
                
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reasoning_summary": reasoning_summary,
            "risks": risks,
            "suggested_actions": suggested_actions,
            "metadata": metadata,
        }


class GatewayReasoningProvider(ReasoningProvider):
    """
    ReasoningProvider implementation that delegates reasoning calls to the Model Gateway.
    """

    def __init__(self, gateway: Any) -> None:
        self.gateway = gateway

    def reason(
        self,
        request: CognitiveRequest,
        context: dict[str, Any],
        decision_type: str,
    ) -> dict[str, Any]:
        import asyncio
        from models.provider import ModelRequest

        model_req = ModelRequest(
            task_id=request.task_id,
            request_type="text",
            capability_required="reasoning",
            prompt=f"Decision Type: {decision_type}. Objective: {request.objective}. Prompt: {request.objective}",
            context=context,
            constraints=request.constraints,
            preferred_model=request.preferred_model or "llama3-70b-8192",
        )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                coro = self.gateway.generate(model_req)
                resp = pool.submit(lambda: asyncio.run(coro)).result()
        else:
            resp = loop.run_until_complete(self.gateway.generate(model_req))

        return {
            "recommendation": resp.output,
            "confidence": 0.90,
            "reasoning_summary": f"Delegated reasoning to Model Gateway using provider: {resp.provider_used}, model: {resp.model_used}.",
            "risks": [],
            "suggested_actions": [],
            "metadata": resp.metadata,
        }


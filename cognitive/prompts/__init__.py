"""
Prompt templates for LLM-based reasoning providers in the Realtimex Cognitive Engine.
"""

from __future__ import annotations

import os

PROMPTS_DIR = os.path.dirname(__file__)

DEFAULT_TEMPLATES = {
    "workflow_planning": (
        "You are the Realtimex Cognitive Engine assisting with Workflow Planning.\n"
        "Goal: {objective}\n"
        "Task ID: {task_id}\n"
        "Constraints: {constraints}\n"
        "Available Capabilities: {available_capabilities}\n"
        "Current Context: {context}\n\n"
        "Generate a step-by-step DAG of steps to achieve the goal. Each step must have:\n"
        "- step_id (unique string)\n"
        "- capability (selected from Available Capabilities)\n"
        "- input_data (dictionary)\n"
        "- dependencies (list of step_ids)\n\n"
        "Return the plan in structured JSON format."
    ),
    "permission_review": (
        "You are the Realtimex Cognitive Engine reviewing execution permissions.\n"
        "Objective: {objective}\n"
        "Required Permissions: {required_permissions}\n"
        "Sandbox / Declared Permissions: {declared_permissions}\n"
        "Current Context: {context}\n\n"
        "Review whether these permissions violate safety constraints. Return recommendation (approve/reject), "
        "confidence score (0-1), list of risks, and suggested actions."
    ),
    "risk_analysis": (
        "You are the Realtimex Cognitive Engine performing Risk Analysis.\n"
        "Goal: {objective}\n"
        "Constraints: {constraints}\n"
        "Current Context: {context}\n\n"
        "Identify scheduling, concurrency, performance, or security risks. Estimate risk level (low/medium/high) "
        "and suggest mitigation actions."
    ),
    "conflict_resolution": (
        "You are the Realtimex Cognitive Engine resolving concurrency conflicts.\n"
        "Goal: {objective}\n"
        "Workflow Steps: {steps}\n"
        "Current Context: {context}\n\n"
        "Check for conflicting resource usage (e.g. concurrent writes to same file). Reorder steps and suggest "
        "sequential dependencies if conflict is detected."
    ),
    "capability_selection": (
        "You are the Realtimex Cognitive Engine selecting capability providers.\n"
        "Objective: {objective}\n"
        "Available Capabilities: {available_capabilities}\n"
        "Current Context: {context}\n\n"
        "Identify which registered capability best fits the objective. If no capability fits, report missing capability."
    ),
    "recovery_recommendation": (
        "You are the Realtimex Cognitive Engine recommending recovery options for task failures.\n"
        "Objective: {objective}\n"
        "Task History & Failure Reason: {failure_reason}\n"
        "Current Context: {context}\n\n"
        "Recommend recovery actions (e.g. retry_with_backoff, fail_fast, notify_admin)."
    ),
}


def load_template(decision_type: str) -> str:
    """
    Load a prompt template for a specific decision type.
    Attempts to read from a corresponding text file in this directory first,
    falling back to the hardcoded defaults if not found.
    """
    filename = f"{decision_type.lower().replace(' ', '_')}.txt"
    filepath = os.path.join(PROMPTS_DIR, filename)

    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass

    # Fallback to defaults
    key = decision_type.lower().replace(" ", "_")
    return DEFAULT_TEMPLATES.get(key, "Execute reasoning for objective: {objective}\nContext: {context}")

"""
Failure Classifier.

Classifies step failures into semantic categories to determine the optimal recovery path.
"""

from __future__ import annotations

from enum import Enum, auto


class FailureType(Enum):
    TRANSIENT = auto()
    PERMISSION = auto()
    RESOURCE = auto()
    PROVIDER = auto()
    LOGIC = auto()
    UNKNOWN = auto()


class FailureClassifier:
    """
    Analyzes step failure reasons to classify the failure type.
    """

    @staticmethod
    def classify(reason: str) -> FailureType:
        """
        Classify a failure reason string into a FailureType category.
        """
        if not reason:
            return FailureType.UNKNOWN

        reason_lower = reason.lower()

        # 1. Resource Error Classifications (quota, rate limits, resource constraints)
        if any(kw in reason_lower for kw in ["rate limit", "exhausted", "quota", "resource", "limit exceeded", "out of memory"]):
            return FailureType.RESOURCE

        # 2. Permission/Security Error Classifications (unauthorized, security, access denied)
        if any(kw in reason_lower for kw in ["permission", "unauthorized", "forbidden", "security", "unregistered", "denied", "access"]):
            return FailureType.PERMISSION

        # 3. Provider Error Classifications (model gateway downtime, external API outage, network error)
        if any(kw in reason_lower for kw in ["provider", "offline", "network", "api key", "connection", "http", "socket", "downtime", "bad gateway"]):
            return FailureType.PROVIDER

        # 4. Transient Error Classifications (timeouts, temporary connection issues)
        if any(kw in reason_lower for kw in ["transient", "temporary", "timeout", "intermittent", "retryable", "try again"]):
            return FailureType.TRANSIENT

        # 5. Logic/Execution Error Classifications (assertions, value errors, simulated test failures)
        if any(kw in reason_lower for kw in ["logic", "permanent", "bug", "valueerror", "runtimeerror", "assertion", "fail permanently", "failed execution"]):
            return FailureType.LOGIC

        return FailureType.UNKNOWN

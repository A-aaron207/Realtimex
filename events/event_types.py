"""
Canonical event type names used by the Realtimex Kernel.

Centralizing event names avoids magic strings scattered across the
codebase and gives future modules (Event Bus subscribers, Recovery
Manager, etc.) a single source of truth to import from.

This module is organized into logical namespaces:
    - KernelEventType: lifecycle events for the Kernel itself.
    - ModuleEventType: discovery, validation, loading events.
    - EventSystemEventType: internal Event Bus / Manager events.
"""

from __future__ import annotations


class KernelEventType:
    """Namespace of event type name constants emitted by the Kernel."""

    # --- Boot sequence (ordered) ---
    KERNEL_BOOT_STARTED = "KernelBootStarted"
    CONFIGURATION_LOADED = "ConfigurationLoaded"
    LOGGER_INITIALIZED = "LoggerInitialized"
    EVENT_BUS_INITIALIZED = "EventBusInitialized"
    SERVICE_REGISTRY_INITIALIZED = "ServiceRegistryInitialized"
    SERVICE_REGISTRY_READY = "ServiceRegistryReady"
    CAPABILITY_REGISTRY_INITIALIZED = "CapabilityRegistryInitialized"
    CAPABILITY_REGISTRY_READY = "CapabilityRegistryReady"
    RECOVERY_INITIALIZED = "RecoveryInitialized"
    MODULES_LOADED = "ModulesLoaded"
    KERNEL_READY = "KernelReady"

    # --- Shutdown ---
    KERNEL_SHUTDOWN_STARTED = "KernelShutdownStarted"
    KERNEL_SHUTDOWN_COMPLETE = "KernelShutdownComplete"
    KERNEL_SHUTDOWN = "KernelShutdown"
    KERNEL_RESTART_REQUESTED = "KernelRestartRequested"

    # --- Operational ---
    KERNEL_OPERATIONAL = "KernelOperational"


class ModuleEventType:
    """Namespace of event type name constants for module lifecycle events."""

    MODULE_DISCOVERED = "ModuleDiscovered"
    MODULE_VALIDATED = "ModuleValidated"
    MODULE_LOADED = "ModuleLoaded"
    MODULE_FAILED = "ModuleFailed"
    MODULE_UNLOADED = "ModuleUnloaded"
    CAPABILITY_REGISTERED = "CapabilityRegistered"
    SERVICE_REGISTERED = "ServiceRegistered"


class EventSystemEventType:
    """Namespace of event type name constants for the Event System itself."""

    EVENT_BUS_STARTED = "EventBusStarted"
    EVENT_BUS_SHUTDOWN = "EventBusShutdown"
    SUBSCRIBER_REGISTERED = "SubscriberRegistered"
    SUBSCRIBER_UNREGISTERED = "SubscriberUnregistered"
    EVENT_DISPATCH_FAILED = "EventDispatchFailed"
    EVENT_PERSISTED = "EventPersisted"
    EVENT_REPLAY_STARTED = "EventReplayStarted"
    EVENT_REPLAY_COMPLETED = "EventReplayCompleted"


class TaskEventType:
    """Namespace of event type name constants for task lifecycle events."""

    TASK_CREATED = "TaskCreated"
    TASK_UPDATED = "TaskUpdated"
    TASK_PAUSED = "TaskPaused"
    TASK_RESUMED = "TaskResumed"
    TASK_CANCELLED = "TaskCancelled"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    TASK_RECOVERED = "TaskRecovered"
    TASK_DELETED = "TaskDeleted"
    PROGRESS_UPDATED = "ProgressUpdated"


class WorkerEventType:
    """Namespace of event type name constants for worker runtime events."""

    WORKER_STARTED = "WorkerStarted"
    WORKER_ASSIGNED = "WorkerAssigned"
    WORKER_EXECUTION_STARTED = "WorkerExecutionStarted"
    WORKER_EXECUTION_FINISHED = "WorkerExecutionFinished"
    WORKER_REPORT_GENERATED = "WorkerReportGenerated"
    WORKER_FAILED = "WorkerFailed"
    WORKER_RECOVERED = "WorkerRecovered"
    WORKER_TERMINATED = "WorkerTerminated"
    HEARTBEAT_RECEIVED = "HeartbeatReceived"


class SchedulerEventType:
    """Namespace of event type name constants for scheduler events."""

    STEP_QUEUED = "StepQueued"
    STEP_DISPATCHED = "StepDispatched"
    WORKER_ALLOCATED = "WorkerAllocated"
    WORKER_RELEASED = "WorkerReleased"
    RETRY_SCHEDULED = "RetryScheduled"
    QUEUE_EMPTY = "QueueEmpty"
    SCHEDULER_STARTED = "SchedulerStarted"
    SCHEDULER_STOPPED = "SchedulerStopped"


# ---------------------------------------------------------------------------
# Backwards compatibility: keep all original constants accessible from
# KernelEventType so that existing call sites (boot.py, shutdown.py,
# loader.py) continue to work without modification.
# ---------------------------------------------------------------------------
# Milestone 2 module constants were originally on KernelEventType.
# Re-expose them for backwards compatibility.
KernelEventType.MODULE_DISCOVERED = ModuleEventType.MODULE_DISCOVERED
KernelEventType.MODULE_VALIDATED = ModuleEventType.MODULE_VALIDATED
KernelEventType.MODULE_LOADED = ModuleEventType.MODULE_LOADED
KernelEventType.MODULE_FAILED = ModuleEventType.MODULE_FAILED
KernelEventType.MODULE_UNLOADED = ModuleEventType.MODULE_UNLOADED
KernelEventType.CAPABILITY_REGISTERED = ModuleEventType.CAPABILITY_REGISTERED
KernelEventType.SERVICE_REGISTERED = ModuleEventType.SERVICE_REGISTERED


class CognitiveEventType:
    """Namespace of event type name constants for cognitive engine events."""

    REASONING_STARTED = "ReasoningStarted"
    REASONING_COMPLETED = "ReasoningCompleted"
    DECISION_GENERATED = "DecisionGenerated"
    VALIDATION_FAILED = "ValidationFailed"
    RECOMMENDATION_ACCEPTED = "RecommendationAccepted"
    RECOMMENDATION_REJECTED = "RecommendationRejected"


class ModelGatewayEventType:
    """Namespace of event type name constants for model gateway events."""

    PROVIDER_REGISTERED = "ProviderRegistered"
    PROVIDER_UNAVAILABLE = "ProviderUnavailable"
    PROVIDER_RECOVERED = "ProviderRecovered"
    MODEL_SELECTED = "ModelSelected"
    REQUEST_STARTED = "RequestStarted"
    REQUEST_COMPLETED = "RequestCompleted"
    REQUEST_FAILED = "RequestFailed"
    FAILOVER_TRIGGERED = "FailoverTriggered"
    QUOTA_EXCEEDED = "QuotaExceeded"
    CACHE_HIT = "CacheHit"
    CACHE_MISS = "CacheMiss"


class MemoryEventType:
    """Namespace of event type name constants for memory lifecycle events."""

    MEMORY_CREATED = "MemoryCreated"
    MEMORY_UPDATED = "MemoryUpdated"
    MEMORY_RETRIEVED = "MemoryRetrieved"
    MEMORY_ARCHIVED = "MemoryArchived"
    MEMORY_DELETED = "MemoryDeleted"
    MEMORY_EXPIRED = "MemoryExpired"


class PermissionEventType:
    """Namespace of event type name constants for permission events."""

    PERMISSION_REQUESTED = "PermissionRequested"
    PERMISSION_APPROVED = "PermissionApproved"
    PERMISSION_DENIED = "PermissionDenied"
    PERMISSION_CACHED = "PermissionCached"
    PERMISSION_EXPIRED = "PermissionExpired"
    POLICY_MATCHED = "PolicyMatched"
    RULE_EVALUATED = "RuleEvaluated"


class RecoveryEventType:
    """Namespace of event type name constants for recovery events."""

    RECOVERY_STARTED = "RecoveryStarted"
    CHECKPOINT_LOADED = "CheckpointLoaded"
    STATE_VALIDATED = "StateValidated"
    TASK_RECOVERED = "TaskRecovered"
    WORKFLOW_RECOVERED = "WorkflowRecovered"
    MEMORY_RECOVERED = "MemoryRecovered"
    RECOVERY_COMPLETED = "RecoveryCompleted"
    RECOVERY_FAILED = "RecoveryFailed"
    SNAPSHOT_CREATED = "SnapshotCreated"
    SNAPSHOT_RESTORED = "SnapshotRestored"


class InterfaceEventType:
    """Namespace of event type name constants for interface layer events."""

    INTERFACE_REGISTERED = "InterfaceRegistered"
    INTERFACE_STARTED = "InterfaceStarted"
    INTERFACE_STOPPED = "InterfaceStopped"
    REQUEST_RECEIVED = "RequestReceived"
    RESPONSE_SENT = "ResponseSent"
    SESSION_CREATED = "SessionCreated"
    SESSION_CLOSED = "SessionClosed"
    CLIENT_CONNECTED = "ClientConnected"
    CLIENT_DISCONNECTED = "ClientDisconnected"


class ConfigurationEventType:
    """Namespace of event type name constants for the Configuration System."""

    CONFIGURATION_LOADED = "ConfigurationLoaded"
    CONFIGURATION_UPDATED = "ConfigurationUpdated"
    CONFIGURATION_RELOADED = "ConfigurationReloaded"
    CONFIGURATION_VALIDATION_FAILED = "ConfigurationValidationFailed"
    PROFILE_CHANGED = "ProfileChanged"
    ENVIRONMENT_CHANGED = "EnvironmentChanged"


"""
Kernel boot sequence.

Defines the ordered sequence of initialization steps the Kernel
performs on startup. Each step is implemented as its own function so
that future milestones can extend, reorder, or instrument individual
steps without touching unrelated logic.

Boot sequence:

    Kernel Boot Started
    -> Load Configuration
    -> Initialize Logger
    -> Initialize Event Manager (Bus + History + Logger + Persistence)
    -> Initialize Service Registry
    -> Initialize Capability Registry
    -> Initialize Recovery Manager
    -> Kernel Ready
    -> Discover Modules
    -> Validate Manifests
    -> Import Modules
    -> Register Services & Capabilities
    -> Kernel Operational
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from capabilities.registry import CapabilityRegistry
from configuration.manager import ConfigurationManager
from configuration.defaults import get_all_defaults
from observability.manager import Observability
from policy.manager import PolicyManager
from security.manager import SecurityManager
from interfaces.manager import InterfaceManager
from memory.manager import MemoryManager
from memory.persistence import FileMemoryPersistence
from memory.policies import MemoryPolicy
from models.gateway import ModelGateway
from cognitive.engine import CognitiveEngine
from cognitive.reasoning import MockReasoningProvider
from permissions.manager import PermissionManager
from permissions.persistence import PermissionPersistence
from permissions.policies import PermissionPolicy
from events.event import Event
from events.event_bus import EventBus
from events.event_types import KernelEventType, ConfigurationEventType
from events.manager import EventManager
from kernel.config_loader import ConfigLoader, KernelConfig
from kernel.logger import KernelLogger
from recovery.manager import RecoveryManager as ProductionRecoveryManager
from recovery.persistence import RecoveryPersistence
from recovery.policies import RecoveryPolicy
from loader.loader import LoadedModule, ModuleLoader
from services.registry import ServiceRegistry
from tasks.api import TaskAPI
from tasks.manager import TaskManager
from tasks.persistence import TaskPersistence
from tasks.recovery import TaskRecovery
from tasks.repository import TaskRepository
from workflow.api import WorkflowAPI
from workflow.manager import WorkflowManager
from workflow.persistence import WorkflowPersistence
from workers.api import WorkerAPI
from workers.manager import WorkerManager
from scheduler.api import SchedulerAPI
from scheduler.scheduler import Scheduler
from kernel.container import DependencyContainer



@dataclass
class BootPaths:
    """
    Filesystem locations used during the boot sequence.

    Attributes:
        config_path: Path to the Kernel's configuration JSON file.
        log_directory: Directory in which log files should be written.
        modules_root: Directory under which module subdirectories live.
    """

    config_path: Path
    log_directory: Path
    modules_root: Path


@dataclass
class BootResult:
    """
    The set of components produced by a successful boot sequence.

    Attributes:
        config_manager: The central Configuration Manager.
        config: The loaded Kernel configuration (legacy view).
        logger: The configured Kernel logger.
        event_bus: The initialized Event Bus (provided by the Event Manager).
        event_manager: The Event Manager that owns bus, history, logger,
            persistence, and replay.
        service_registry: The initialized Service Registry.
        capability_registry: The initialized Capability Registry.
        recovery_manager: The initialized Recovery Manager.
        module_loader: The Module Loader used to discover and load modules.
        loaded_modules: The modules successfully loaded during boot.
    """

    config_manager: ConfigurationManager
    config: KernelConfig
    logger: logging.Logger
    event_bus: EventBus
    event_manager: EventManager
    service_registry: ServiceRegistry
    capability_registry: CapabilityRegistry
    recovery_manager: RecoveryManager
    module_loader: ModuleLoader
    task_manager: TaskManager
    task_api: TaskAPI
    workflow_manager: WorkflowManager
    workflow_api: WorkflowAPI
    worker_manager: WorkerManager
    worker_api: WorkerAPI
    scheduler: Scheduler
    scheduler_api: SchedulerAPI
    loaded_modules: list[LoadedModule]
    
    # Integrated Subsystems
    observability: Observability
    policy_manager: PolicyManager
    security_manager: SecurityManager
    interface_manager: InterfaceManager
    memory_manager: MemoryManager
    model_gateway: ModelGateway
    cognitive_engine: CognitiveEngine
    permission_manager: PermissionManager
    dependency_container: DependencyContainer



def emit_boot_started(logger: logging.Logger) -> None:
    """
    Log that the boot sequence has started.

    This is the very first boot step and runs before the Event Bus
    exists, so it can only be logged directly. Once the Event Bus is
    initialized later in the sequence, a corresponding
    KernelBootStarted event is emitted through it as well, giving any
    future subscriber a durable record of boot start.

    Args:
        logger: A logger to record the boot start, even before the
            full Kernel logger is configured.
    """
    logger.info("Kernel Boot Started.")


def load_configuration(config_path: Path) -> KernelConfig:
    """
    Boot step: load Kernel configuration from disk.

    Args:
        config_path: Path to the configuration JSON file.

    Returns:
        The loaded KernelConfig.
    """
    loader = ConfigLoader(config_path=config_path)
    return loader.load()


def initialize_logger(log_directory: Path, config: KernelConfig) -> logging.Logger:
    """
    Boot step: configure the centralized Kernel logger.

    Args:
        log_directory: Directory in which the log file should be written.
        config: The loaded Kernel configuration, providing log level and filename.

    Returns:
        The configured root Kernel logger.
    """
    return KernelLogger.configure(
        log_directory=log_directory,
        log_filename=config.log_filename,
        level=config.log_level,
    )


def initialize_event_manager(
    logger: logging.Logger, log_directory: Path, config: KernelConfig
) -> EventManager:
    """
    Boot step: initialize the Event Manager with all its components.

    The Event Manager assembles the Event Bus, Event History, Event
    Logger, Event Persistence, and Event Replay into a single
    coordinated unit.

    Args:
        logger: The Kernel logger for diagnostic output.
        log_directory: Directory where event logs are written.
        config: The loaded Kernel configuration (event_bus section
            may specify history_max_size, persistence_filename, etc.).

    Returns:
        A fully initialized EventManager.
    """
    event_bus_config = config.raw.get("event_bus", {})
    history_max_size = event_bus_config.get("history_max_size", 10_000)
    persistence_filename = event_bus_config.get("persistence_filename", "events.jsonl")
    event_log_filename = event_bus_config.get("event_log_filename", "event_log.jsonl")

    return EventManager(
        logger=logger,
        log_directory=log_directory,
        history_max_size=history_max_size,
        persistence_filename=persistence_filename,
        event_log_filename=event_log_filename,
    )


def initialize_event_bus(logger: logging.Logger) -> EventBus:
    """
    Boot step: initialize a standalone Event Bus.

    .. deprecated::
        Prefer ``initialize_event_manager()`` which creates a full
        Event Manager.  This function is retained for backwards
        compatibility with tests or minimal boot paths that only need
        a bare bus.

    Args:
        logger: The Kernel logger the Event Bus will log through.

    Returns:
        A new EventBus instance.
    """
    return EventBus(logger=logger)


def initialize_service_registry() -> ServiceRegistry:
    """
    Boot step: initialize the Service Registry.

    Returns:
        A new, empty ServiceRegistry instance.
    """
    return ServiceRegistry()


def initialize_capability_registry() -> CapabilityRegistry:
    """
    Boot step: initialize the Capability Registry.

    Returns:
        A new, empty CapabilityRegistry instance.
    """
    return CapabilityRegistry()


def initialize_recovery_manager(
    config_manager: ConfigurationManager,
    event_bus: EventBus,
    logger: logging.Logger,
    log_directory: Path,
) -> ProductionRecoveryManager:
    """
    Boot step: initialize the production Recovery Manager.

    Args:
        config_manager: The central Configuration Manager.
        event_bus: Global EventBus.
        logger: Centralized logger.
        log_directory: Directory for recovery persistence files.

    Returns:
        A new production RecoveryManager instance.
    """
    recovery_enabled = config_manager.get("recovery_manager.enabled", True)
    recovery_interval = config_manager.get("recovery.checkpoint_interval", 300)
    recovery_max_checkpoints = config_manager.get("recovery.max_checkpoints", 10)
    recovery_retention = config_manager.get("recovery.retention_days", 7)
    
    recovery_persistence = RecoveryPersistence(directory=log_directory / "recovery")
    recovery_policy = RecoveryPolicy(
        checkpoint_interval_seconds=float(recovery_interval),
        max_retained_checkpoints=int(recovery_max_checkpoints),
        snapshot_retention_days=int(recovery_retention),
        recovery_strategy="fail_safe",
    )
    
    return ProductionRecoveryManager(
        persistence=recovery_persistence,
        event_bus=event_bus,
        policy=recovery_policy,
        logger=logger,
        enabled=recovery_enabled,
    )


def build_module_loader(
    modules_root: Path,
    capability_registry: CapabilityRegistry,
    service_registry: ServiceRegistry,
    event_bus: EventBus,
    logger: logging.Logger,
) -> ModuleLoader:
    """
    Boot step: construct the Module Loader.

    Loading itself (discover -> validate -> import -> register) is
    deliberately triggered later, once the Kernel has reached READY,
    so that "Kernel Ready" and "Kernel Operational" remain distinct,
    observable milestones in the boot sequence.

    Args:
        modules_root: Directory under which module subdirectories live.
        capability_registry: Registry that module capabilities are
            registered into.
        service_registry: Registry used to check module service dependencies.
        event_bus: Event Bus used to announce loading progress.
        logger: Logger for structured diagnostic output.

    Returns:
        A configured, not-yet-run ModuleLoader instance.
    """
    return ModuleLoader(
        modules_root=modules_root,
        capability_registry=capability_registry,
        service_registry=service_registry,
        event_bus=event_bus,
        logger=logger,
    )


def run_boot_sequence(paths: BootPaths) -> BootResult:
    """
    Execute the full Kernel boot sequence in order, emitting an event
    after each step.

    Args:
        paths: Filesystem locations required during boot.

    Returns:
        A BootResult containing every component initialized during boot.
    """
    bootstrap_logger = logging.getLogger("realtimex.bootstrap")
    if not bootstrap_logger.handlers:
        bootstrap_logger.addHandler(logging.StreamHandler())
        bootstrap_logger.setLevel(logging.INFO)
        bootstrap_logger.propagate = False

    emit_boot_started(logger=bootstrap_logger)

    config = load_configuration(paths.config_path)
    logger = initialize_logger(paths.log_directory, config)

    # --- Milestone 3: full Event Manager replaces the bare EventBus ---
    event_manager = initialize_event_manager(logger, paths.log_directory, config)
    event_bus = event_manager.event_bus

    # Instantiate ConfigurationManager early so other subsystems can use it
    config_manager = ConfigurationManager(event_bus=event_bus, config_dir=str(paths.config_path.parent))
    config_manager.initialize()

    event_bus.emit(Event(name=KernelEventType.KERNEL_BOOT_STARTED, source="kernel.boot"))
    event_bus.emit(
        Event(
            name=KernelEventType.CONFIGURATION_LOADED,
            source="kernel.boot",
            payload={"config_path": str(paths.config_path)},
        )
    )
    event_bus.emit(Event(name=KernelEventType.LOGGER_INITIALIZED, source="kernel.boot"))
    event_bus.emit(Event(name=KernelEventType.EVENT_BUS_INITIALIZED, source="kernel.boot"))

    service_registry = initialize_service_registry()
    from services.base import SimpleService
    service_registry.register(SimpleService("logger", {"logger": logger}))
    event_bus.emit(Event(name=KernelEventType.SERVICE_REGISTRY_INITIALIZED, source="kernel.boot"))

    capability_registry = initialize_capability_registry()
    event_bus.emit(Event(name=KernelEventType.CAPABILITY_REGISTRY_INITIALIZED, source="kernel.boot"))

    recovery_manager = initialize_recovery_manager(config_manager, event_bus, logger, paths.log_directory)
    event_bus.emit(Event(name=KernelEventType.RECOVERY_INITIALIZED, source="kernel.boot"))

    # --- Milestone 4: Task System Initialization and Recovery ---
    tasks_dir_name = config_manager.get("task_system.tasks_directory", "tasks")
    task_persistence = TaskPersistence(directory=paths.log_directory / tasks_dir_name)
    task_repository = TaskRepository(persistence=task_persistence)
    task_manager = TaskManager(repository=task_repository, event_bus=event_bus, logger=logger)
    task_api = TaskAPI(repository=task_repository)

    # Execute task recovery for any active tasks on startup
    task_recovery = TaskRecovery(repository=task_repository, event_bus=event_bus, logger=logger)
    recovered_count = task_recovery.recover_tasks()

    event_bus.emit(
        Event(
            name="TaskSystemInitialized",
            source="kernel.boot",
            payload={"recovered_tasks": recovered_count},
        )
    )

    # --- Milestone 5: Workflow Engine Initialization ---
    wf_dir_name = config_manager.get("workflow_engine.workflows_directory", "workflows")
    wf_persistence = WorkflowPersistence(directory=paths.log_directory / wf_dir_name)
    workflow_manager = WorkflowManager(persistence=wf_persistence, event_bus=event_bus, logger=logger)
    workflow_api = WorkflowAPI(manager=workflow_manager)

    event_bus.emit(
        Event(
            name="WorkflowEngineInitialized",
            source="kernel.boot",
            payload={},
        )
    )

    # --- Milestone 6: Worker Runtime Initialization ---
    class BootResultWrapper:
        def __init__(self):
            self.boot_result = None

    result_wrapper = BootResultWrapper()
    worker_manager = WorkerManager(
        event_bus=event_bus,
        loaded_modules_provider=lambda: result_wrapper.boot_result.loaded_modules if result_wrapper.boot_result else [],
        logger=logger,
    )
    worker_api = WorkerAPI(manager=worker_manager)

    event_bus.emit(
        Event(
            name="WorkerRuntimeInitialized",
            source="kernel.boot",
            payload={},
        )
    )

    # --- Milestone 7: Scheduler Initialization ---
    scheduler_max_retries = config_manager.get("scheduler.max_retries", 3)
    scheduler_retry_delay = config_manager.get("scheduler.retry_delay", 1.0)
    scheduler = Scheduler(
        task_manager=task_manager,
        workflow_manager=workflow_manager,
        capability_registry=capability_registry,
        worker_manager=worker_manager,
        event_bus=event_bus,
        logger=logger,
        max_retries=scheduler_max_retries,
        retry_delay=scheduler_retry_delay,
    )
    scheduler_api = SchedulerAPI(scheduler=scheduler)

    event_bus.emit(
        Event(
            name="SchedulerInitialized",
            source="kernel.boot",
            payload={},
        )
    )

    # --- Integration of remaining subsystems ---
    
    # 2. Observability
    log_file = paths.log_directory / "realtimex.log"
    audit_file = paths.log_directory / "security_audit.log"
    observability = Observability(
        event_bus=event_bus,
        config_dir=str(paths.config_path.parent),
        log_filepath=str(log_file),
        audit_filepath=str(audit_file)
    )
    
    # 3. Policy Manager
    policy_dir = paths.config_path.parent / "policies"
    os.makedirs(policy_dir, exist_ok=True)
    policy_manager = PolicyManager(event_bus=event_bus, policy_dir=str(policy_dir))
    
    # 4. Security Manager
    sec_audit_file = paths.log_directory / "security_violations.log"
    security_manager = SecurityManager(event_bus=event_bus, audit_filepath=str(sec_audit_file))
    
    # 5. Interface Manager
    rest_port = config_manager.get("interfaces.rest_port", 8000)
    ws_port = config_manager.get("interfaces.websocket_port", 8001)

    interface_manager = InterfaceManager(event_bus=event_bus)
    from interfaces.cli.interface import CLIInterface
    from interfaces.api.rest import RESTInterface
    from interfaces.api.websocket import WebSocketInterface
    interface_manager.register_interface(CLIInterface())
    interface_manager.register_interface(RESTInterface(port=rest_port))
    interface_manager.register_interface(WebSocketInterface(port=ws_port))
    interface_manager.start_all()
    
    # 6. Memory Manager
    memory_persistence = FileMemoryPersistence(directory=paths.log_directory / "memory")
    memory_policy = MemoryPolicy()
    memory_manager = MemoryManager(
        persistence=memory_persistence,
        event_bus=event_bus,
        policy=memory_policy
    )
    
    # 7. Model Gateway
    model_gateway = ModelGateway(event_bus=event_bus)
    service_registry.register(SimpleService("model_gateway", {"gateway": model_gateway}))
    
    # 8. Cognitive Engine
    cognitive_engine = CognitiveEngine(
        reasoning_provider=MockReasoningProvider(),
        task_manager=task_manager,
        workflow_manager=workflow_manager,
        event_manager=event_manager
    )
    
    # 9. Permission Manager
    permission_persistence = PermissionPersistence(directory=paths.log_directory / "permissions")
    permission_policy = PermissionPolicy()
    permission_manager = PermissionManager(
        persistence=permission_persistence,
        event_bus=event_bus,
        cognitive_engine=cognitive_engine,
        policy=permission_policy
    )

    module_loader = build_module_loader(
        modules_root=paths.modules_root,
        capability_registry=capability_registry,
        service_registry=service_registry,
        event_bus=event_bus,
        logger=logger,
    )

    # Start Scheduler loop only after all systems are fully booted and resolved
    scheduler.start()

    # Populate Dependency Container
    dependency_container = DependencyContainer()
    dependency_container.register("config_manager", config_manager)
    dependency_container.register("event_manager", event_manager)
    dependency_container.register("event_bus", event_bus)
    dependency_container.register("service_registry", service_registry)
    dependency_container.register("capability_registry", capability_registry)
    dependency_container.register("recovery_manager", recovery_manager)
    dependency_container.register("task_manager", task_manager)
    dependency_container.register("workflow_manager", workflow_manager)
    dependency_container.register("worker_manager", worker_manager)
    dependency_container.register("scheduler", scheduler)
    dependency_container.register("observability", observability)
    dependency_container.register("policy_manager", policy_manager)
    dependency_container.register("security_manager", security_manager)
    dependency_container.register("interface_manager", interface_manager)
    dependency_container.register("memory_manager", memory_manager)
    dependency_container.register("model_gateway", model_gateway)
    dependency_container.register("cognitive_engine", cognitive_engine)
    dependency_container.register("permission_manager", permission_manager)

    boot_result = BootResult(
        config_manager=config_manager,
        config=config,
        logger=logger,
        event_bus=event_bus,
        event_manager=event_manager,
        service_registry=service_registry,
        capability_registry=capability_registry,
        recovery_manager=recovery_manager,
        module_loader=module_loader,
        task_manager=task_manager,
        task_api=task_api,
        workflow_manager=workflow_manager,
        workflow_api=workflow_api,
        worker_manager=worker_manager,
        worker_api=worker_api,
        scheduler=scheduler,
        scheduler_api=scheduler_api,
        loaded_modules=[],
        observability=observability,
        policy_manager=policy_manager,
        security_manager=security_manager,
        interface_manager=interface_manager,
        memory_manager=memory_manager,
        model_gateway=model_gateway,
        cognitive_engine=cognitive_engine,
        permission_manager=permission_manager,
        dependency_container=dependency_container,
    )
    result_wrapper.boot_result = boot_result

    return boot_result

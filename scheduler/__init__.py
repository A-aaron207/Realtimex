"""
Realtimex Scheduler package.

Responsible for dispatching ready workflow steps to appropriate workers,
respecting task priorities, structural dependencies, and worker availability.

Components:
    - Scheduler: scheduler core thread loop.
    - SchedulerAPI: control and query interface.
    - DispatchQueue: prioritized step execution buffer.
    - ResourceAllocator: matches steps to pools and acquires workers.
    - DependencyResolver: validates pre-conditions before scheduling.
    - Dispatcher: executes steps asynchronously in background threads.
    - RetryManager: coordinates retries and exponential backoff timers.
    - SchedulerMonitor: monitors queues, rates, wait times, and execution logs.
"""

from scheduler.api import SchedulerAPI  # noqa: F401
from scheduler.exceptions import (  # noqa: F401
    AllocationError,
    DependencyError,
    DispatchError,
    QueueError,
    SchedulerError,
)
from scheduler.scheduler import Scheduler  # noqa: F401
from scheduler.queue import DispatchQueue  # noqa: F401
from scheduler.allocator import ResourceAllocator  # noqa: F401
from scheduler.dependency import DependencyResolver  # noqa: F401
from scheduler.dispatcher import Dispatcher  # noqa: F401
from scheduler.retry import RetryManager  # noqa: F401
from scheduler.monitor import SchedulerMonitor  # noqa: F401
from scheduler.policies import (  # noqa: F401
    QueueItem,
    SchedulingPolicy,
    FIFOPolicy,
    PriorityPolicy,
    EarliestReadyPolicy,
)

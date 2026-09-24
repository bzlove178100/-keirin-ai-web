"""Dependency-light autonomous-agent foundation.

This package intentionally contains no embedded network credentials. Concrete provider
clients are injected by the hosting runtime so permissions and side effects remain
explicit and testable.
"""

from .adapters import Capability, CallableReadOnlyGitHubAdapter, ToolRegistry
from .model import (
    ActionResult,
    ArtifactState,
    ArtifactUpdate,
    StepSpec,
    TaskSpec,
    TaskState,
)
from .orchestrator import AgentOrchestrator, PreflightReport
from .reporting import DailyActivityReport, RevenueMetric, build_activity_report
from .runner import AgentRunner, BlockedAction, RunOutcome
from .store import FileStateStore

__all__ = [
    "ActionResult",
    "AgentOrchestrator",
    "AgentRunner",
    "ArtifactState",
    "ArtifactUpdate",
    "BlockedAction",
    "CallableReadOnlyGitHubAdapter",
    "Capability",
    "DailyActivityReport",
    "FileStateStore",
    "PreflightReport",
    "RevenueMetric",
    "RunOutcome",
    "StepSpec",
    "TaskSpec",
    "TaskState",
    "ToolRegistry",
    "build_activity_report",
]

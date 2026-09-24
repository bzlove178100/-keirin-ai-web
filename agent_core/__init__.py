"""Dependency-light autonomous-agent foundation.

This package intentionally contains no embedded network credentials. Concrete provider
clients are injected by the hosting runtime so permissions and side effects remain
explicit and testable.
"""

from .adapters import Capability, CallableReadOnlyGitHubAdapter, ToolRegistry
from .delivery import BridgeReportDelivery, DeliveryResult, ReportDelivery
from .job_router import JOB_ROUTES, JobPlan, JobRequest, JobRoute, JobRouter
from .model import (
    ActionResult,
    ArtifactState,
    ArtifactUpdate,
    StepSpec,
    TaskSpec,
    TaskState,
)
from .orchestrator import AgentOrchestrator, PreflightReport
from .provider_adapters import FileArtifactAdapter, ReadOnlySupabaseStatusAdapter
from .reporting import DailyActivityReport, RevenueMetric, build_activity_report
from .runner import AgentRunner, BlockedAction, RunOutcome
from .runtime import BoundRuntime, RuntimeBinding, RuntimeManifest
from .runtime_bridge import BridgeResponse, BridgeToolAdapter, RuntimeBridge
from .scheduling import DAILY_REPORT_2100_JST, DailySchedule
from .store import FileStateStore

__all__ = [
    "ActionResult",
    "AgentOrchestrator",
    "AgentRunner",
    "ArtifactState",
    "ArtifactUpdate",
    "BlockedAction",
    "BoundRuntime",
    "BridgeReportDelivery",
    "BridgeResponse",
    "BridgeToolAdapter",
    "CallableReadOnlyGitHubAdapter",
    "Capability",
    "DAILY_REPORT_2100_JST",
    "DailyActivityReport",
    "DailySchedule",
    "DeliveryResult",
    "FileArtifactAdapter",
    "FileStateStore",
    "JOB_ROUTES",
    "JobPlan",
    "JobRequest",
    "JobRoute",
    "JobRouter",
    "PreflightReport",
    "ReadOnlySupabaseStatusAdapter",
    "ReportDelivery",
    "RevenueMetric",
    "RunOutcome",
    "RuntimeBinding",
    "RuntimeBridge",
    "RuntimeManifest",
    "StepSpec",
    "TaskSpec",
    "TaskState",
    "ToolRegistry",
    "build_activity_report",
]

"""Dependency-light autonomous-agent foundation.

This package intentionally contains no embedded network credentials. Concrete provider
clients are injected by the hosting runtime so permissions and side effects remain
explicit and testable.
"""

from .activation import (
    ACTIVATION_SCHEMA_VERSION,
    HostedActivationManifest,
    load_hosted_activation_manifest,
    validate_hosted_activation_manifest,
)
from .adapters import Capability, CallableReadOnlyGitHubAdapter, ToolRegistry
from .capability_catalog import CapabilityContract, capability_by_action, capability_catalog
from .delivery import BridgeReportDelivery, DeliveryResult, ReportDelivery
from .hosted_activity import (
    HostedActivityClient,
    HostedActivityError,
    HostedActivityEvent,
    HostedActivityIntegrityError,
)
from .hosted_checkpoint import (
    HostedCheckpointClient,
    HostedCheckpointConflict,
    HostedCheckpointError,
    HostedCheckpointIntegrityError,
    HostedCheckpointRecord,
    HostedCheckpointSummary,
)
from .hosted_queue import (
    HostedQueueClient,
    HostedQueueConflict,
    HostedQueueError,
    HostedQueueIntegrityError,
    HostedQueueLease,
)
from .hosted_readonly_worker import (
    HostedExecutionNotAuthorized,
    HostedLeaseStateStore,
    HostedReadOnlyWorker,
    HostedReadOnlyWorkerResult,
)
from .hosted_recovery import (
    HostedRecoveryInspector,
    HostedRecoveryIntegrityError,
    HostedRecoveryProposal,
    HostedRecoveryReport,
)
from .hosted_transport import HostedTransportError, SupabaseEdgeTransport
from .hosted_worker import HostedWorkerCoordinator, HostedWorkerDecision
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
    "ACTIVATION_SCHEMA_VERSION",
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
    "CapabilityContract",
    "DAILY_REPORT_2100_JST",
    "DailyActivityReport",
    "DailySchedule",
    "DeliveryResult",
    "FileArtifactAdapter",
    "FileStateStore",
    "HostedActivationManifest",
    "HostedActivityClient",
    "HostedActivityError",
    "HostedActivityEvent",
    "HostedActivityIntegrityError",
    "HostedCheckpointClient",
    "HostedCheckpointConflict",
    "HostedCheckpointError",
    "HostedCheckpointIntegrityError",
    "HostedCheckpointRecord",
    "HostedCheckpointSummary",
    "HostedExecutionNotAuthorized",
    "HostedLeaseStateStore",
    "HostedQueueClient",
    "HostedQueueConflict",
    "HostedQueueError",
    "HostedQueueIntegrityError",
    "HostedQueueLease",
    "HostedReadOnlyWorker",
    "HostedReadOnlyWorkerResult",
    "HostedRecoveryInspector",
    "HostedRecoveryIntegrityError",
    "HostedRecoveryProposal",
    "HostedRecoveryReport",
    "HostedTransportError",
    "HostedWorkerCoordinator",
    "HostedWorkerDecision",
    "PreflightReport",
    "ReadOnlySupabaseStatusAdapter",
    "ReportDelivery",
    "RevenueMetric",
    "RunOutcome",
    "RuntimeBinding",
    "RuntimeBridge",
    "RuntimeManifest",
    "StepSpec",
    "SupabaseEdgeTransport",
    "TaskSpec",
    "TaskState",
    "ToolRegistry",
    "build_activity_report",
    "capability_by_action",
    "capability_catalog",
    "load_hosted_activation_manifest",
    "validate_hosted_activation_manifest",
]

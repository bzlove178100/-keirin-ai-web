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
from .credential_provider import (
    CredentialProvider,
    CredentialSnapshot,
    StaticInMemoryCredentialProvider,
    CredentialProviderError,
    CredentialScopeError,
    CredentialLifetimeError,
    CredentialRevokedError,
)
from .delivery import BridgeReportDelivery, DeliveryResult, ReportDelivery
from .exact_task_queue import BoundExactTaskQueueClient, ExactTaskQueueClient
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
    HostedCheckpointNotFound,
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
from .refresh_credentials import (
    AccessCredentialGrant,
    CredentialAuthBlocked,
    CredentialBinding,
    CredentialRefreshInProgress,
    HostCredentialSource,
    RefreshingCredentialProvider,
)
from .reporting import DailyActivityReport, RevenueMetric, build_activity_report
from .runner import AgentRunner, BlockedAction, RunOutcome
from .runtime import BoundRuntime, RuntimeBinding, RuntimeManifest
from .runtime_bridge import BridgeResponse, BridgeToolAdapter, RuntimeBridge
from .scheduling import DAILY_REPORT_2100_JST, DailySchedule
from .store import FileStateStore
from .trusted_run_enqueue import TrustedRunAlreadyUsed, TrustedRunEnqueuer, TrustedRunEnqueueResult
from .trusted_run_instance import (
    TRUSTED_RUN_ID_PREFIX,
    TrustedRunInstance,
    build_trusted_status_run_spec,
    is_trusted_status_run_spec,
    trusted_status_template_spec,
    validate_trusted_status_run_spec,
)
from .versioned_secret_store import (
    InMemoryVersionedSecretStore,
    RefreshExchange,
    RefreshExchangeAmbiguous,
    RefreshExchangeRejected,
    RefreshExchangeResult,
    RefreshSecretRecord,
    SecretStoreAmbiguousWrite,
    SecretStoreConflict,
    SecretStoreError,
    VersionedHostCredentialSource,
    VersionedSecretStore,
)

__all__ = [
    "AccessCredentialGrant",
    "CredentialAuthBlocked",
    "CredentialBinding",
    "CredentialRefreshInProgress",
    "HostCredentialSource",
    "RefreshingCredentialProvider",

    "CredentialProvider",
    "CredentialSnapshot",
    "StaticInMemoryCredentialProvider",
    "CredentialProviderError",
    "CredentialScopeError",
    "CredentialLifetimeError",
    "CredentialRevokedError",

    "InMemoryVersionedSecretStore",
    "RefreshExchange",
    "RefreshExchangeAmbiguous",
    "RefreshExchangeRejected",
    "RefreshExchangeResult",
    "RefreshSecretRecord",
    "SecretStoreAmbiguousWrite",
    "SecretStoreConflict",
    "SecretStoreError",
    "VersionedHostCredentialSource",
    "VersionedSecretStore",

    "ACTIVATION_SCHEMA_VERSION",
    "ActionResult",
    "AgentOrchestrator",
    "AgentRunner",
    "ArtifactState",
    "ArtifactUpdate",
    "BlockedAction",
    "BoundExactTaskQueueClient",
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
    "ExactTaskQueueClient",
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
    "HostedCheckpointNotFound",
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
    "TRUSTED_RUN_ID_PREFIX",
    "TaskSpec",
    "TaskState",
    "ToolRegistry",
    "TrustedRunAlreadyUsed",
    "TrustedRunEnqueueResult",
    "TrustedRunEnqueuer",
    "TrustedRunInstance",
    "build_activity_report",
    "build_trusted_status_run_spec",
    "capability_by_action",
    "capability_catalog",
    "is_trusted_status_run_spec",
    "load_hosted_activation_manifest",
    "trusted_status_template_spec",
    "validate_hosted_activation_manifest",
    "validate_trusted_status_run_spec",
]
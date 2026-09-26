from __future__ import annotations

from agent_core.hosted_transport import ExactClaimRoutingTransport, SupabaseEdgeTransport
from agent_core.model import TaskSpec
from tools.agent_hosted_repository_worker import HostedRepositoryStatusWorker


def prepare_exact_run_instance_worker(
    *,
    project_url: str,
    publishable_key: str,
    owner_bearer_token: str,
    github_token: str,
    target_spec: TaskSpec,
    execution_authorized: bool = False,
    requester=None,
    api_get=None,
    hard_deadline_seconds: float = 180.0,
):
    """Construct a worker whose exact claim uses a separate narrow Edge function.

    Supplying credentials never authorizes execution by itself. The worker still
    requires ``execution_authorized is True`` before any queue/provider I/O.
    """
    default_transport = SupabaseEdgeTransport(
        project_url=project_url,
        publishable_key=publishable_key,
        bearer_token=owner_bearer_token,
        function_slug="agent-runtime-dev",
        requester=requester,
    )
    exact_claim_transport = SupabaseEdgeTransport(
        project_url=project_url,
        publishable_key=publishable_key,
        bearer_token=owner_bearer_token,
        function_slug="agent-exact-claim-dev",
        requester=requester,
    )
    transport = ExactClaimRoutingTransport(
        default_transport=default_transport,
        exact_claim_transport=exact_claim_transport,
    )
    return HostedRepositoryStatusWorker(
        transport=transport,
        github_token=github_token,
        execution_authorized=execution_authorized,
        api_get=api_get,
        hard_deadline_seconds=hard_deadline_seconds,
        target_spec=target_spec,
    )

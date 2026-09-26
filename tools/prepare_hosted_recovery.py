from __future__ import annotations

from agent_core import HostedActivityClient, HostedQueueClient, HostedRecoveryInspector, SupabaseEdgeTransport


def prepare_hosted_recovery(*, project_url: str, publishable_key: str, owner_bearer_token: str):
    """Construct a read-only recovery inspector for the existing hosted task state.

    Supplying credentials does not mutate queue state or execute a task. Network I/O
    starts only when ``inspect(spec)`` is called on the returned inspector.
    """
    transport = SupabaseEdgeTransport(
        project_url=project_url,
        publishable_key=publishable_key,
        bearer_token=owner_bearer_token,
    )
    return HostedRecoveryInspector(
        queue=HostedQueueClient(transport),
        activity=HostedActivityClient(transport),
    )

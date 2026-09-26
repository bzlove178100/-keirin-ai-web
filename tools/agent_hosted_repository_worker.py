"""Preparation-only composition. No CLI, scheduler, environment activation or writes to GitHub."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import threading

from agent_core.adapters import ToolRegistry
from agent_core.hosted_activity import HostedActivityClient
from agent_core.hosted_queue import HostedQueueClient
from agent_core.hosted_readonly_worker import HostedReadOnlyWorker
from agent_core.hosted_transport import SupabaseEdgeTransport
from agent_core.model import TaskSpec
from agent_core.runtime_bridge import BridgeToolAdapter
from tools.agent_github_readonly_host import runtime_manifest
from tools.agent_github_sha_bridge import ShaPinnedGitHubReadOnlyBridge


class HostedRunInterrupted(BaseException):
    """Non-retry signal: stop the host immediately; reconcile durable state separately.

    Deliberately bypasses AgentRunner's Exception retry loop. The caller must not
    restart run_next automatically. Like process interruption, no cleanup POST is
    attempted because the preceding POST may already have committed.
    """


class _FencedBridge(ShaPinnedGitHubReadOnlyBridge):
    guard = None

    def _api_get(self, path):
        if self.guard is None:
            raise HostedRunInterrupted("hosted_request_guard_missing")
        self.guard()
        result = super()._api_get(path)
        self.guard()
        return result


def trusted_status_spec() -> TaskSpec:
    path = Path(__file__).resolve().parents[1] / "agent_core/examples/keirin_readonly_status_task.json"
    return TaskSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


class HostedRepositoryStatusWorker(HostedReadOnlyWorker):
    """One scoped task per explicit call, disabled by default.

    Observation and verification evidence use the existing append-only activity
    store, tagged with TaskSpec fingerprint/revision/generation. No schema change.
    Interruption is blocked for explicit reconciliation, not automatic replay.
    """

    def __init__(self, *, transport, github_token, execution_authorized=False,
                 api_get=None, clock=time.monotonic, utcnow=lambda: datetime.now(timezone.utc)):
        self._run_lock = threading.Lock()
        self._expected_fingerprint = trusted_status_spec().fingerprint()
        self._clock = clock
        self._utcnow = utcnow
        self._bridge = _FencedBridge(token=github_token, api_get=api_get)
        registry = ToolRegistry()
        registry.register(BridgeToolAdapter(name="hosted-github-readonly", bridge=self._bridge,
            capabilities=tuple(b.capability() for b in runtime_manifest().bindings)))
        super().__init__(queue=HostedQueueClient(transport), activity=HostedActivityClient(transport),
                         registry=registry, execution_authorized=execution_authorized)

    def _scope_failure(self, lease):
        if lease.spec.fingerprint() != self._expected_fingerprint:
            return "hosted_task_outside_trusted_scope"
        if lease.attempt_count != 1 or lease.state.attempts or lease.state.completed_steps:
            return "hosted_prior_attempt_requires_reconciliation"
        return None

    def _guarded_actions(self, store=None):
        if store is None:
            raise HostedRunInterrupted("hosted_lease_store_required")
        deadline = self._clock() + 180.0
        observation = None

        def check_time():
            if self._clock() >= deadline:
                raise HostedRunInterrupted("hosted_run_deadline_exceeded")
            expires = datetime.fromisoformat(store.lease.lease_expires_at.replace("Z", "+00:00"))
            if (expires - self._utcnow()).total_seconds() <= 30:
                raise HostedRunInterrupted("hosted_lease_budget_insufficient")

        def fence():
            try:
                check_time()
                # Uses the current authoritative revision/generation, never reclaims.
                store.save_state(store.load_state(store.lease.task_id))
                check_time()
            except Exception:
                raise HostedRunInterrupted("hosted_fence_uncertain_requires_reconciliation") from None

        def record(kind, data, context):
            fence()
            payload = {
                    "spec_fingerprint": self._expected_fingerprint,
                    "lease_generation": store.lease.lease_generation,
                    "revision": store.lease.revision,
                    "evidence": deepcopy(data),
                }
            ack = self.activity.append(task_id=store.lease.task_id, event_type=kind,
                                       step_id=context["step_id"], payload=payload)
            if ack.event_type != kind or ack.step_id != context["step_id"] or ack.payload != payload:
                raise HostedRunInterrupted("hosted_evidence_ack_mismatch")
            # Acknowledgement is necessary but not sufficient: check the fence again.
            fence()

        self._bridge.guard = fence
        actions = super()._guarded_actions(store)

        def read(args, context):
            nonlocal observation
            try:
                result = actions["github.read_main"](args, context)
                record("github_observation", result.data, context)
                observation = deepcopy(result.data)
                return result
            except Exception:
                raise HostedRunInterrupted("hosted_observation_uncertain_requires_reconciliation") from None

        def verify(args, context):
            try:
                if observation is None or args.get("action_result", {}).get("data") != observation:
                    raise HostedRunInterrupted("hosted_observation_mismatch")
                result = actions["github.verify_ci"](args, context)
                record("github_verification", result.data, context)
                return result
            except Exception:
                raise HostedRunInterrupted("hosted_verification_uncertain_requires_reconciliation") from None

        return {"github.read_main": read, "github.verify_ci": verify}

    def run_next(self, *, worker_id, lease_seconds=120):
        if not self._run_lock.acquire(blocking=False):
            raise HostedRunInterrupted("hosted_worker_already_running")
        try:
            return super().run_next(worker_id=worker_id, lease_seconds=lease_seconds)
        finally:
            # No lease store or observation remains captured by the bridge after a run.
            self._bridge.guard = None
            self._run_lock.release()


def prepare_repository_worker(*, project_url, publishable_key, owner_bearer_token,
                              github_token, execution_authorized=False, requester=None,
                              api_get=None):
    """Construct only. Supplying credentials does not claim a task or authorize execution."""
    transport = SupabaseEdgeTransport(project_url=project_url, publishable_key=publishable_key,
                                     bearer_token=owner_bearer_token, requester=requester)
    return HostedRepositoryStatusWorker(transport=transport, github_token=github_token,
                                       execution_authorized=execution_authorized, api_get=api_get)

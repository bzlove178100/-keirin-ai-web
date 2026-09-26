from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.adapters import Capability, ToolRegistry  # noqa: E402
from agent_core.credential_adapter import CredentialRequirement, require_credential_snapshot  # noqa: E402
from agent_core.credential_stack import build_durable_credential_bound_adapter  # noqa: E402
from agent_core.durable_secret_store import (  # noqa: E402
    DurableSecretBackendAmbiguousWrite,
    DurableSecretBackendConflict,
    DurableVersionedSecretStore,
    SECRET_RECORD_SCHEMA_VERSION,
)
from agent_core.model import ActionResult, StepSpec, TaskSpec  # noqa: E402
from agent_core.refresh_credentials import AccessCredentialGrant, CredentialBinding  # noqa: E402
from agent_core.runner import AgentRunner  # noqa: E402
from agent_core.store import FileStateStore  # noqa: E402
from agent_core.versioned_secret_store import RefreshExchangeResult  # noqa: E402

NOW = 1_800_000_000
OLD_REFRESH = "old-refresh-secret-fixture"
ROTATED_REFRESH = "rotated-refresh-secret-fixture"
ACCESS = "access-token-fixture"
BINDING = CredentialBinding("fixture-provider", "fixture-account", ("provider.read",))


def record_payload(*, state="ready", version=0, refresh_secret=OLD_REFRESH, generation=0,
                   active_attempt_id=None, last_attempt_id=None, failure=None):
    return {
        "schema_version": SECRET_RECORD_SCHEMA_VERSION,
        "provider_id": BINDING.provider_id,
        "account_id": BINDING.account_id,
        "capabilities": list(BINDING.capabilities),
        "version": version,
        "state": state,
        "refresh_secret": refresh_secret,
        "refresh_generation": generation,
        "active_attempt_id": active_attempt_id,
        "last_attempt_id": last_attempt_id,
        "failure": failure,
    }


class FakeDurableBackend:
    def __init__(self, payload=None):
        self.key = DurableVersionedSecretStore.key_for(BINDING)
        self.payload = deepcopy(payload if payload is not None else record_payload())
        self.cas_calls = 0
        self.conflict_once = False
        self.ambiguous_after_apply_version: int | None = None

    def read(self, key):
        if key != self.key:
            return None
        return deepcopy(self.payload)

    def compare_and_swap(self, key, *, expected_version, replacement):
        self.cas_calls += 1
        if key != self.key:
            raise DurableSecretBackendConflict("wrong-key-secret-payload")
        if self.conflict_once:
            self.conflict_once = False
            raise DurableSecretBackendConflict("backend-conflict-secret-payload")
        if self.payload is None or self.payload.get("version") != expected_version:
            raise DurableSecretBackendConflict("stale-secret-payload")
        committed = deepcopy(dict(replacement))
        self.payload = committed
        if committed.get("version") == self.ambiguous_after_apply_version:
            raise DurableSecretBackendAmbiguousWrite("ambiguous-secret-payload")
        return deepcopy(committed)


class FakeExchange:
    def __init__(self, *, ambiguous=False):
        self.calls = 0
        self.ambiguous = ambiguous
        self.seen_refresh: str | None = None

    def exchange(self, binding, *, refresh_secret, attempt_id, minimum_ttl_seconds):
        self.calls += 1
        self.seen_refresh = refresh_secret
        if self.ambiguous:
            raise RuntimeError(f"transport lost after consuming {refresh_secret}")
        self.assert_binding = binding
        return RefreshExchangeResult(
            grant=AccessCredentialGrant(
                provider_id=binding.provider_id,
                account_id=binding.account_id,
                capabilities=binding.capabilities,
                access_token=ACCESS,
                issued_at=NOW - 1,
                expires_at=NOW + max(3600, minimum_ttl_seconds + 1),
            ),
            rotated_refresh_secret=ROTATED_REFRESH,
        )


class FakeProviderAdapter:
    name = "credential-stack-provider"

    def __init__(self):
        self.calls = 0
        self.seen_access: str | None = None

    def capabilities(self):
        return (Capability("provider.read", "read", required_permissions=("provider:read",)),)

    def actions(self):
        def read(args, context):
            self.calls += 1
            snapshot = require_credential_snapshot(context)
            self.seen_access = snapshot.secret("access_token")
            return ActionResult(message="provider read complete", data={"rows": 1})
        return {"provider.read": read}


def build_adapter(backend, exchange, provider_adapter):
    return build_durable_credential_bound_adapter(
        adapter=provider_adapter,
        binding=BINDING,
        backend=backend,
        exchange=exchange,
        requirements=(CredentialRequirement("provider.read", ("provider.read",), minimum_ttl_seconds=300),),
        clock=lambda: NOW,
        attempt_id_factory=lambda: "attempt-0001",
    )


def task():
    return TaskSpec(
        task_id="credential-stack-task",
        title="Credential stack task",
        goal="Exercise the offline durable credential composition",
        allowed_actions=("provider.read",),
        steps=(StepSpec(step_id="read", action="provider.read", retry_safe=False, max_attempts=1),),
    )


def runtime_text(base):
    chunks = []
    for path in Path(base).rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


class CredentialStackCompositionTest(unittest.TestCase):
    def test_success_rotates_refresh_before_provider_action_and_persists_no_credentials(self):
        backend = FakeDurableBackend()
        exchange = FakeExchange()
        provider_adapter = FakeProviderAdapter()
        registry = ToolRegistry()
        registry.register(build_adapter(backend, exchange, provider_adapter))
        spec = task()
        fingerprint = spec.fingerprint()

        with tempfile.TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            outcome = AgentRunner(store, registry.actions()).run(spec)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(exchange.calls, 1)
            self.assertEqual(exchange.seen_refresh, OLD_REFRESH)
            self.assertEqual(provider_adapter.calls, 1)
            self.assertEqual(provider_adapter.seen_access, ACCESS)
            self.assertEqual(backend.payload["state"], "ready")
            self.assertEqual(backend.payload["version"], 2)
            self.assertEqual(backend.payload["refresh_generation"], 1)
            self.assertEqual(backend.payload["refresh_secret"], ROTATED_REFRESH)
            self.assertEqual(backend.payload["last_attempt_id"], "attempt-0001")
            persisted = runtime_text(tmp)
            self.assertNotIn(OLD_REFRESH, persisted)
            self.assertNotIn(ROTATED_REFRESH, persisted)
            self.assertNotIn(ACCESS, persisted)
            self.assertEqual(spec.fingerprint(), fingerprint)

            # Completed work remains terminal even though the credential rotated.
            second = AgentRunner(store, registry.actions()).run(spec)
            self.assertEqual(second.status, "completed")
            self.assertEqual(exchange.calls, 1)
            self.assertEqual(provider_adapter.calls, 1)

    def test_ambiguous_exchange_blocks_durably_before_provider_action(self):
        backend = FakeDurableBackend()
        exchange = FakeExchange(ambiguous=True)
        provider_adapter = FakeProviderAdapter()
        registry = ToolRegistry()
        registry.register(build_adapter(backend, exchange, provider_adapter))

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_blocked:credential_unavailable")
            self.assertEqual(provider_adapter.calls, 0)
            self.assertEqual(exchange.calls, 1)
            self.assertEqual(backend.payload["state"], "blocked_ambiguous")
            self.assertEqual(backend.payload["version"], 2)
            self.assertEqual(backend.payload["failure"], "refresh_outcome_ambiguous")
            persisted = runtime_text(tmp)
            self.assertNotIn(OLD_REFRESH, persisted)
            self.assertNotIn(ROTATED_REFRESH, persisted)
            self.assertNotIn(ACCESS, persisted)

    def test_ambiguous_commit_with_matching_readback_is_accepted_once(self):
        backend = FakeDurableBackend()
        backend.ambiguous_after_apply_version = 2
        exchange = FakeExchange()
        provider_adapter = FakeProviderAdapter()
        registry = ToolRegistry()
        registry.register(build_adapter(backend, exchange, provider_adapter))

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task())
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(exchange.calls, 1)
            self.assertEqual(provider_adapter.calls, 1)
            self.assertEqual(backend.payload["state"], "ready")
            self.assertEqual(backend.payload["version"], 2)
            self.assertEqual(backend.payload["refresh_secret"], ROTATED_REFRESH)
            self.assertNotIn(ACCESS, runtime_text(tmp))

    def test_claim_conflict_blocks_before_exchange_or_provider_action(self):
        backend = FakeDurableBackend()
        backend.conflict_once = True
        exchange = FakeExchange()
        provider_adapter = FakeProviderAdapter()
        registry = ToolRegistry()
        registry.register(build_adapter(backend, exchange, provider_adapter))

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_blocked:credential_unavailable")
            self.assertEqual(exchange.calls, 0)
            self.assertEqual(provider_adapter.calls, 0)
            self.assertEqual(backend.payload["state"], "ready")
            self.assertEqual(backend.payload["version"], 0)
            self.assertNotIn(OLD_REFRESH, runtime_text(tmp))

    def test_revoked_durable_record_blocks_before_exchange_or_provider_action(self):
        backend = FakeDurableBackend(record_payload(state="revoked", refresh_secret=None))
        exchange = FakeExchange()
        provider_adapter = FakeProviderAdapter()
        registry = ToolRegistry()
        registry.register(build_adapter(backend, exchange, provider_adapter))

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_blocked:credential_unavailable")
            self.assertEqual(exchange.calls, 0)
            self.assertEqual(provider_adapter.calls, 0)
            self.assertNotIn(ACCESS, runtime_text(tmp))

    def test_composition_repr_does_not_expose_backend_refresh_material(self):
        backend = FakeDurableBackend()
        exchange = FakeExchange()
        adapter = build_adapter(backend, exchange, FakeProviderAdapter())
        rendered = repr(adapter)
        self.assertNotIn(OLD_REFRESH, rendered)
        self.assertNotIn(ROTATED_REFRESH, rendered)
        self.assertNotIn(ACCESS, rendered)
        self.assertIn("<redacted>", rendered)


if __name__ == "__main__":
    unittest.main()

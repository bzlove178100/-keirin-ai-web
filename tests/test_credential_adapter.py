from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.adapters import Capability, ToolRegistry  # noqa: E402
from agent_core.credential_adapter import (  # noqa: E402
    CredentialBoundToolAdapter,
    CredentialRequirement,
    require_credential_snapshot,
)
from agent_core.credential_provider import StaticInMemoryCredentialProvider  # noqa: E402
from agent_core.model import ActionResult, StepSpec, TaskSpec  # noqa: E402
from agent_core.refresh_credentials import CredentialAuthBlocked  # noqa: E402
from agent_core.runner import AgentRunner, BlockedAction  # noqa: E402
from agent_core.store import FileStateStore  # noqa: E402

SECRET = "credential-adapter-secret-fixture"


class FakeProviderAdapter:
    name = "fake-provider"

    def __init__(self):
        self.calls: list[str] = []
        self.seen_secret: str | None = None

    def capabilities(self):
        return (
            Capability("provider.read", "read", required_permissions=("provider:read",)),
            Capability("provider.verify", "read", required_permissions=("provider:read",)),
        )

    def actions(self):
        return {
            "provider.read": self.read,
            "provider.verify": self.verify,
        }

    def read(self, args, context):
        self.calls.append("read")
        snapshot = require_credential_snapshot(context)
        self.seen_secret = snapshot.secret("access_token")
        return ActionResult(message="provider read complete", data={"rows": 1})

    def verify(self, args, context):
        self.calls.append("verify")
        snapshot = require_credential_snapshot(context)
        self.seen_secret = snapshot.secret("access_token")
        return {"verified": True}


class OneActionAdapter:
    name = "one-action"

    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def capabilities(self):
        return (Capability("provider.read", "read"),)

    def actions(self):
        def action(args, context):
            self.calls += 1
            if self.callback:
                return self.callback(args, context)
            return ActionResult(message="ok")
        return {"provider.read": action}


class FailingProvider:
    refresh_capable = True

    def __init__(self, *, unexpected=False):
        self.calls = 0
        self.unexpected = unexpected

    def snapshot(self, *args, **kwargs):
        self.calls += 1
        if self.unexpected:
            raise RuntimeError(SECRET)
        raise CredentialAuthBlocked(SECRET)


def provider(*, capabilities=("provider.read", "provider.verify"), secret=SECRET):
    now = int(time.time())
    return StaticInMemoryCredentialProvider(
        provider_id="fixture-provider",
        account_label="fixture-owner",
        capabilities=capabilities,
        secrets={"access_token": secret},
        issued_at=now - 5,
        expires_at=now + 3600,
    )


def task(*, verify=True):
    allowed = ["provider.read"]
    verify_action = "provider.verify" if verify else None
    if verify:
        allowed.append("provider.verify")
    return TaskSpec(
        task_id="credential-gated-task",
        title="Credential gated task",
        goal="Block before provider action when auth is unavailable",
        allowed_actions=tuple(allowed),
        steps=(
            StepSpec(
                step_id="read",
                action="provider.read",
                verify_action=verify_action,
                retry_safe=False,
                max_attempts=1,
            ),
        ),
    )


def all_runtime_text(base: str) -> str:
    chunks: list[str] = []
    for path in Path(base).rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


class CredentialBoundAdapterTest(unittest.TestCase):
    def test_success_injects_access_snapshot_only_into_local_action_context(self):
        inner = FakeProviderAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            provider(),
            (
                CredentialRequirement("provider.read", ("provider.read",)),
                CredentialRequirement("provider.verify", ("provider.verify",)),
            ),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task())
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(inner.calls, ["read", "verify"])
            self.assertEqual(inner.seen_secret, SECRET)
            persisted = all_runtime_text(tmp)
            self.assertNotIn(SECRET, persisted)
            self.assertNotIn("_agent_credential_snapshot_v1", persisted)

    def test_typed_auth_failure_blocks_before_underlying_action_and_redacts_context(self):
        failing = FailingProvider()
        inner = OneActionAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            failing,
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            outcome = AgentRunner(store, registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_blocked:credential_unavailable")
            self.assertIsNone(outcome.last_error)
            self.assertEqual(failing.calls, 1)
            self.assertEqual(inner.calls, 0)
            persisted = all_runtime_text(tmp)
            self.assertNotIn(SECRET, persisted)
            # Terminal blocked state cannot silently retry after credentials change.
            second = AgentRunner(store, registry.actions()).run(task(verify=False))
            self.assertEqual(second.status, "blocked")
            self.assertEqual(failing.calls, 1)
            self.assertEqual(inner.calls, 0)

    def test_unexpected_credential_provider_failure_is_fixed_and_redacted(self):
        failing = FailingProvider(unexpected=True)
        inner = OneActionAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            failing,
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_blocked:credential_provider_failure")
            self.assertEqual(inner.calls, 0)
            self.assertNotIn(SECRET, all_runtime_text(tmp))

    def test_scope_failure_blocks_before_underlying_action(self):
        inner = OneActionAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("other.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(outcome.blocked_reason, "action_blocked:credential_unavailable")
        self.assertEqual(inner.calls, 0)

    def test_known_expiry_policy_is_enforced_by_gate(self):
        no_expiry = StaticInMemoryCredentialProvider(
            provider_id="fixture-provider",
            account_label="fixture-owner",
            capabilities=("provider.read",),
            secrets={"access_token": SECRET},
        )
        inner = OneActionAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            no_expiry,
            (CredentialRequirement("provider.read", ("provider.read",), require_known_expiry=True),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(inner.calls, 0)

    def test_requirements_must_cover_every_adapter_action(self):
        with self.assertRaisesRegex(ValueError, "credential_requirements_must_cover_all_actions"):
            CredentialBoundToolAdapter(
                FakeProviderAdapter(),
                provider(),
                (CredentialRequirement("provider.read", ("provider.read",)),),
            )

    def test_credential_snapshot_cannot_be_returned_as_action_result(self):
        def echo_snapshot(args, context):
            return {"data": {"snapshot": require_credential_snapshot(context)}}

        inner = OneActionAdapter(callback=echo_snapshot)
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_error_requires_reconciliation")
            self.assertIn("credential_material_return_forbidden", outcome.last_error or "")
            self.assertNotIn(SECRET, all_runtime_text(tmp))

    def test_access_token_cannot_be_returned_in_action_result(self):
        def echo_secret(args, context):
            snapshot = require_credential_snapshot(context)
            return ActionResult(
                message="provider response",
                data={"authorization": f"Bearer {snapshot.secret('access_token')}"},
            )

        inner = OneActionAdapter(callback=echo_secret)
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_error_requires_reconciliation")
            self.assertEqual(outcome.last_error, "RuntimeError:credential_material_return_forbidden")
            self.assertNotIn(SECRET, all_runtime_text(tmp))

    def test_underlying_provider_exception_is_fixed_before_runner_persistence(self):
        def fail_with_secret(args, context):
            require_credential_snapshot(context)
            raise RuntimeError(f"provider payload carried {SECRET}")

        inner = OneActionAdapter(callback=fail_with_secret)
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_error_requires_reconciliation")
            self.assertEqual(outcome.last_error, "RuntimeError:credential_bound_provider_action_failed")
            self.assertNotIn(SECRET, all_runtime_text(tmp))

    def test_underlying_blocked_action_reason_is_not_forwarded(self):
        def block_with_secret(args, context):
            require_credential_snapshot(context)
            raise BlockedAction(f"provider rejected {SECRET}")

        inner = OneActionAdapter(callback=block_with_secret)
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), registry.actions()).run(task(verify=False))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(
                outcome.blocked_reason,
                "action_blocked:credential_bound_provider_action_blocked",
            )
            self.assertIsNone(outcome.last_error)
            self.assertNotIn(SECRET, all_runtime_text(tmp))

    def test_provider_exception_context_is_not_retained_by_wrapper(self):
        def fail_with_secret(args, context):
            require_credential_snapshot(context)
            raise RuntimeError(SECRET)

        gated = CredentialBoundToolAdapter(
            OneActionAdapter(callback=fail_with_secret),
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        action = gated.actions()["provider.read"]
        with self.assertRaisesRegex(RuntimeError, "credential_bound_provider_action_failed") as caught:
            action({}, {})
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(SECRET, repr(caught.exception))

    def test_adapter_repr_and_registry_description_remain_secret_free(self):
        inner = OneActionAdapter()
        gated = CredentialBoundToolAdapter(
            inner,
            provider(capabilities=("provider.read",)),
            (CredentialRequirement("provider.read", ("provider.read",)),),
        )
        registry = ToolRegistry()
        registry.register(gated)
        rendered = repr(gated) + json.dumps(registry.describe(), sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertIn("<redacted>", repr(gated))


if __name__ == "__main__":
    unittest.main()

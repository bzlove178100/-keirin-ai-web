from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from threading import Event, Thread
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.refresh_credentials import (  # noqa: E402
    AccessCredentialGrant,
    CredentialAuthBlocked,
    CredentialBinding,
    CredentialRefreshInProgress,
    RefreshingCredentialProvider,
)
from agent_core.credential_provider import CredentialRevokedError  # noqa: E402
from agent_core.versioned_secret_store import (  # noqa: E402
    InMemoryVersionedSecretStore,
    RefreshExchangeAmbiguous,
    RefreshExchangeRejected,
    RefreshExchangeResult,
    RefreshSecretRecord,
    SecretStoreAmbiguousWrite,
    SecretStoreConflict,
    VersionedHostCredentialSource,
)

NOW = 1_800_000_000
BINDING = CredentialBinding("fixture-provider", "fixture-owner", ("repository.read",))
OLD_REFRESH = "old-refresh-fixture-secret"
NEW_REFRESH = "new-refresh-fixture-secret"
ACCESS = "access-fixture-secret"
ATTEMPT = "attempt-0001"


def access_grant(**changes):
    base = AccessCredentialGrant(
        BINDING.provider_id,
        BINDING.account_id,
        BINDING.capabilities,
        ACCESS,
        NOW,
        NOW + 900,
    )
    return replace(base, **changes)


class FakeExchange:
    def __init__(self):
        self.calls = 0
        self.callback = None
        self.result = RefreshExchangeResult(access_grant(), NEW_REFRESH)
        self.seen_secret = None
        self.seen_attempt = None

    def exchange(self, binding, *, refresh_secret, attempt_id, minimum_ttl_seconds):
        self.calls += 1
        self.seen_secret = refresh_secret
        self.seen_attempt = attempt_id
        self.binding = binding
        self.minimum = minimum_ttl_seconds
        if self.callback:
            return self.callback()
        return self.result


class FaultStore(InMemoryVersionedSecretStore):
    """Inject one CAS fault either before or after the selected write is applied."""

    def __init__(self, *, state: str, timing: str):
        super().__init__()
        self.fault_state = state
        self.timing = timing
        self.triggered = False

    def compare_and_swap(self, binding, *, expected_version, replacement):
        if not self.triggered and replacement.state == self.fault_state:
            self.triggered = True
            if self.timing == "before":
                raise SecretStoreAmbiguousWrite("fixture_ambiguous_write")
            if self.timing == "after":
                super().compare_and_swap(
                    binding,
                    expected_version=expected_version,
                    replacement=replacement,
                )
                raise SecretStoreAmbiguousWrite("fixture_ambiguous_write")
        return super().compare_and_swap(
            binding,
            expected_version=expected_version,
            replacement=replacement,
        )


class VersionedSecretStoreTest(unittest.TestCase):
    def make(self, store=None, exchange=None, *, attempt=ATTEMPT):
        store = store or InMemoryVersionedSecretStore()
        exchange = exchange or FakeExchange()
        try:
            store.seed(BINDING, OLD_REFRESH)
        except SecretStoreConflict:
            pass
        source = VersionedHostCredentialSource(
            BINDING,
            store,
            exchange,
            attempt_id_factory=lambda: attempt,
        )
        return store, exchange, source

    def test_record_safe_metadata_and_repr_never_include_refresh_secret(self):
        store, _, _ = self.make()
        record = store.read(BINDING)
        rendered = repr(record) + json.dumps(record.to_safe_dict(), sort_keys=True)
        self.assertNotIn(OLD_REFRESH, rendered)
        self.assertEqual(record.to_safe_dict()["refresh_secret_present"], True)
        self.assertEqual(record.state, "ready")
        self.assertEqual(record.version, 0)

    def test_store_cas_requires_exact_version_and_next_version(self):
        store, _, _ = self.make()
        current = store.read(BINDING)
        replacement = replace(current, version=1, state="blocked_auth", failure="fixture")
        saved = store.compare_and_swap(BINDING, expected_version=0, replacement=replacement)
        self.assertEqual(saved.version, 1)
        with self.assertRaisesRegex(SecretStoreConflict, "secret_store_version_conflict"):
            store.compare_and_swap(BINDING, expected_version=0, replacement=replacement)
        with self.assertRaisesRegex(ValueError, "secret_store_replacement_version_invalid"):
            store.compare_and_swap(
                BINDING,
                expected_version=1,
                replacement=replace(saved, version=3),
            )

    def test_success_claims_then_persists_rotated_secret_before_return(self):
        store, exchange, source = self.make()

        def inspect_claim():
            current = store.read(BINDING)
            self.assertEqual(current.state, "refreshing")
            self.assertEqual(current.active_attempt_id, ATTEMPT)
            self.assertEqual(current.refresh_secret, OLD_REFRESH)
            return exchange.result

        exchange.callback = inspect_claim
        grant = source.refresh_access(BINDING, minimum_ttl_seconds=300)
        final = store.read(BINDING)
        self.assertEqual(grant.access_token, ACCESS)
        self.assertEqual(final.state, "ready")
        self.assertEqual(final.version, 2)
        self.assertEqual(final.refresh_generation, 1)
        self.assertEqual(final.refresh_secret, NEW_REFRESH)
        self.assertEqual(final.last_attempt_id, ATTEMPT)
        self.assertIsNone(final.active_attempt_id)
        self.assertEqual(exchange.calls, 1)

    def test_two_sources_share_store_and_only_one_can_exchange(self):
        store = InMemoryVersionedSecretStore()
        store.seed(BINDING, OLD_REFRESH)
        entered, release = Event(), Event()
        first_exchange = FakeExchange()

        def slow():
            entered.set()
            if not release.wait(3):
                raise RuntimeError("fixture_timeout")
            return first_exchange.result

        first_exchange.callback = slow
        first = VersionedHostCredentialSource(
            BINDING, store, first_exchange, attempt_id_factory=lambda: "attempt-first"
        )
        second_exchange = FakeExchange()
        second = VersionedHostCredentialSource(
            BINDING, store, second_exchange, attempt_id_factory=lambda: "attempt-second"
        )
        errors = []

        def run_first():
            try:
                first.refresh_access(BINDING, minimum_ttl_seconds=300)
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=run_first)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(store.read(BINDING).state, "refreshing")
            with self.assertRaises(CredentialRefreshInProgress):
                second.refresh_access(BINDING, minimum_ttl_seconds=300)
            self.assertEqual(second_exchange.calls, 0)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(first_exchange.calls, 1)
        self.assertEqual(store.read(BINDING).state, "ready")

    def test_ambiguous_exchange_blocks_durably_and_never_auto_retries(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(
            RefreshExchangeAmbiguous("secret-provider-payload")
        )
        with self.assertRaisesRegex(CredentialAuthBlocked, "credential_refresh_outcome_ambiguous") as caught:
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertIsNone(caught.exception.__context__)
        blocked = store.read(BINDING)
        self.assertEqual(blocked.state, "blocked_ambiguous")
        self.assertEqual(blocked.failure, "refresh_outcome_ambiguous")
        self.assertEqual(blocked.last_attempt_id, ATTEMPT)
        self.assertEqual(exchange.calls, 1)
        with self.assertRaises(CredentialAuthBlocked):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(exchange.calls, 1)
        self.assertNotIn("secret-provider-payload", repr(blocked))

    def test_untyped_exchange_failure_is_ambiguous_not_retryable(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(RuntimeError(OLD_REFRESH))
        with self.assertRaises(CredentialAuthBlocked) as caught:
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(store.read(BINDING).state, "blocked_ambiguous")
        self.assertNotIn(OLD_REFRESH, str(caught.exception))

    def test_definite_provider_rejection_blocks_auth_without_rotation(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(
            RefreshExchangeRejected("provider-detail-must-not-escape")
        )
        with self.assertRaisesRegex(CredentialAuthBlocked, "credential_refresh_rejected"):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        blocked = store.read(BINDING)
        self.assertEqual(blocked.state, "blocked_auth")
        self.assertEqual(blocked.refresh_secret, OLD_REFRESH)
        self.assertEqual(blocked.refresh_generation, 0)
        self.assertEqual(exchange.calls, 1)

    def test_malformed_success_is_treated_as_ambiguous_rotation(self):
        variants = (
            object(),
            RefreshExchangeResult(access_grant(provider_id="other"), NEW_REFRESH),
            RefreshExchangeResult(access_grant(capabilities=("repository.write",)), NEW_REFRESH),
            RefreshExchangeResult(access_grant(access_token=""), NEW_REFRESH),
            RefreshExchangeResult(access_grant(expires_at=NOW + 100), NEW_REFRESH),
            RefreshExchangeResult(access_grant(), ""),
        )
        for result in variants:
            with self.subTest(result=repr(result)):
                store, exchange, source = self.make()
                exchange.result = result
                with self.assertRaises(CredentialAuthBlocked):
                    source.refresh_access(BINDING, minimum_ttl_seconds=300)
                self.assertEqual(store.read(BINDING).state, "blocked_ambiguous")
                self.assertEqual(exchange.calls, 1)

    def test_claim_ambiguous_after_apply_is_confirmed_by_readback(self):
        store = FaultStore(state="refreshing", timing="after")
        _, exchange, source = self.make(store=store)
        grant = source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(grant.access_token, ACCESS)
        self.assertTrue(store.triggered)
        self.assertEqual(exchange.calls, 1)
        self.assertEqual(store.read(BINDING).state, "ready")

    def test_claim_ambiguous_before_apply_never_contacts_provider(self):
        store = FaultStore(state="refreshing", timing="before")
        _, exchange, source = self.make(store=store)
        with self.assertRaisesRegex(CredentialAuthBlocked, "credential_refresh_claim_ambiguous"):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(exchange.calls, 0)
        self.assertEqual(store.read(BINDING).state, "ready")

    def test_success_commit_ambiguous_after_apply_is_confirmed_by_readback(self):
        store = FaultStore(state="ready", timing="after")
        # Seed itself writes ready, so arm the fault only after seed.
        store.fault_state = "seed-disabled"
        store.seed(BINDING, OLD_REFRESH)
        store.fault_state = "ready"
        exchange = FakeExchange()
        source = VersionedHostCredentialSource(
            BINDING, store, exchange, attempt_id_factory=lambda: ATTEMPT
        )
        grant = source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(grant.access_token, ACCESS)
        self.assertTrue(store.triggered)
        final = store.read(BINDING)
        self.assertEqual(final.state, "ready")
        self.assertEqual(final.refresh_secret, NEW_REFRESH)
        self.assertEqual(final.refresh_generation, 1)

    def test_success_commit_ambiguous_before_apply_blocks_for_recovery(self):
        store = FaultStore(state="ready", timing="before")
        store.fault_state = "seed-disabled"
        store.seed(BINDING, OLD_REFRESH)
        store.fault_state = "ready"
        exchange = FakeExchange()
        source = VersionedHostCredentialSource(
            BINDING, store, exchange, attempt_id_factory=lambda: ATTEMPT
        )
        with self.assertRaisesRegex(CredentialAuthBlocked, "credential_refresh_persistence_ambiguous"):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        final = store.read(BINDING)
        self.assertEqual(final.state, "blocked_ambiguous")
        self.assertEqual(final.failure, "secret_store_commit_ambiguous")
        self.assertEqual(final.refresh_secret, OLD_REFRESH)
        self.assertEqual(exchange.calls, 1)

    def test_recover_not_applied_requires_exact_version_and_attempt(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(RuntimeError("ambiguous"))
        with self.assertRaises(CredentialAuthBlocked):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        blocked = store.read(BINDING)
        with self.assertRaises(SecretStoreConflict):
            source.recover_ambiguous_not_applied(
                expected_version=blocked.version - 1,
                attempt_id=ATTEMPT,
            )
        with self.assertRaises(CredentialAuthBlocked):
            source.recover_ambiguous_not_applied(
                expected_version=blocked.version,
                attempt_id="wrong-attempt",
            )
        recovered = source.recover_ambiguous_not_applied(
            expected_version=blocked.version,
            attempt_id=ATTEMPT,
        )
        self.assertEqual(recovered.state, "ready")
        self.assertEqual(recovered.refresh_secret, OLD_REFRESH)
        self.assertEqual(recovered.refresh_generation, 0)
        self.assertEqual(recovered.version, blocked.version + 1)

    def test_recover_applied_requires_verified_rotated_secret_and_increments_generation(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(RuntimeError("ambiguous"))
        with self.assertRaises(CredentialAuthBlocked):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        blocked = store.read(BINDING)
        recovered = source.recover_ambiguous_with_rotated_secret(
            expected_version=blocked.version,
            attempt_id=ATTEMPT,
            rotated_refresh_secret=NEW_REFRESH,
        )
        self.assertEqual(recovered.state, "ready")
        self.assertEqual(recovered.refresh_secret, NEW_REFRESH)
        self.assertEqual(recovered.refresh_generation, 1)
        safe = repr(recovered) + json.dumps(recovered.to_safe_dict(), sort_keys=True)
        self.assertNotIn(NEW_REFRESH, safe)

    def test_recovered_store_requires_new_provider_after_refreshing_provider_blocks(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(RuntimeError("ambiguous"))
        provider = RefreshingCredentialProvider(BINDING, source, clock=lambda: NOW)
        with self.assertRaises(CredentialAuthBlocked):
            provider.snapshot(BINDING.capabilities)
        blocked = store.read(BINDING)
        source.recover_ambiguous_not_applied(
            expected_version=blocked.version,
            attempt_id=ATTEMPT,
        )
        exchange.callback = None
        with self.assertRaises(CredentialAuthBlocked):
            provider.snapshot(BINDING.capabilities)
        fresh_provider = RefreshingCredentialProvider(BINDING, source, clock=lambda: NOW)
        view = fresh_provider.snapshot(BINDING.capabilities)
        self.assertEqual(view.secret("access_token"), ACCESS)
        self.assertEqual(exchange.calls, 2)

    def test_revoke_clears_store_secret_and_is_terminal(self):
        store, exchange, source = self.make()
        revoked = source.revoke()
        self.assertEqual(revoked.state, "revoked")
        self.assertIsNone(revoked.refresh_secret)
        with self.assertRaises(CredentialRevokedError):
            source.assert_available()
        with self.assertRaises(CredentialRevokedError):
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(exchange.calls, 0)

    def test_source_integrates_with_access_only_refresh_provider(self):
        store, exchange, source = self.make()
        provider = RefreshingCredentialProvider(BINDING, source, clock=lambda: NOW)
        snapshot = provider.snapshot(BINDING.capabilities)
        self.assertEqual(snapshot.secret_names, ("access_token",))
        self.assertEqual(snapshot.secret("access_token"), ACCESS)
        self.assertEqual(provider.to_safe_dict()["state"], "ready")
        persisted = store.read(BINDING)
        self.assertEqual(persisted.refresh_generation, 1)
        self.assertEqual(persisted.refresh_secret, NEW_REFRESH)
        safe = repr(snapshot) + repr(provider) + repr(persisted)
        for secret in (OLD_REFRESH, NEW_REFRESH, ACCESS):
            self.assertNotIn(secret, safe)

    def test_keyboard_interrupt_marks_ambiguous_before_propagation(self):
        store, exchange, source = self.make()
        exchange.callback = lambda: (_ for _ in ()).throw(KeyboardInterrupt(OLD_REFRESH))
        with self.assertRaises(KeyboardInterrupt) as caught:
            source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(str(caught.exception), "credential_refresh_interrupted")
        self.assertEqual(store.read(BINDING).state, "blocked_ambiguous")
        self.assertNotIn(OLD_REFRESH, str(caught.exception))


if __name__ == "__main__":
    unittest.main()

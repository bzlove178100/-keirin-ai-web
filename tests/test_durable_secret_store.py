from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.durable_secret_store import (  # noqa: E402
    DurableSecretBackendAmbiguousWrite,
    DurableSecretBackendConflict,
    DurableSecretBackendUnavailable,
    DurableVersionedSecretStore,
    SECRET_RECORD_SCHEMA_VERSION,
    _encode_record,
)
from agent_core.refresh_credentials import (  # noqa: E402
    AccessCredentialGrant,
    CredentialAuthBlocked,
    CredentialBinding,
)
from agent_core.versioned_secret_store import (  # noqa: E402
    RefreshExchangeResult,
    RefreshSecretRecord,
    SecretStoreAmbiguousWrite,
    SecretStoreConflict,
    SecretStoreError,
    VersionedHostCredentialSource,
)

BINDING = CredentialBinding("fixture-provider", "fixture-owner", ("repository.read",))
OLD_REFRESH = "old-refresh-fixture-secret"
NEW_REFRESH = "new-refresh-fixture-secret"
ACCESS = "access-fixture-secret"
NOW = 1_800_000_000


class FakeDurableBackend:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.read_failure: str | None = None
        self.cas_failure: str | None = None
        self.mutate_readback = False
        self.cas_calls = 0

    def seed(self, key: str, record: RefreshSecretRecord):
        self.rows[key] = deepcopy(_encode_record(record))

    def read(self, key: str):
        if self.read_failure == "unavailable":
            raise DurableSecretBackendUnavailable(OLD_REFRESH)
        if self.read_failure == "unexpected":
            raise RuntimeError(OLD_REFRESH)
        value = self.rows.get(key)
        return deepcopy(value) if value is not None else None

    def compare_and_swap(self, key, *, expected_version, replacement):
        self.cas_calls += 1
        current = self.rows.get(key)
        if self.cas_failure == "conflict":
            raise DurableSecretBackendConflict(OLD_REFRESH)
        if self.cas_failure == "unavailable":
            raise DurableSecretBackendUnavailable(OLD_REFRESH)
        if self.cas_failure == "unexpected":
            raise RuntimeError(OLD_REFRESH)
        if current is None or current.get("version") != expected_version:
            raise DurableSecretBackendConflict("stale-with-secret=" + OLD_REFRESH)
        if self.cas_failure == "ambiguous_before":
            raise DurableSecretBackendAmbiguousWrite(OLD_REFRESH)
        self.rows[key] = deepcopy(dict(replacement))
        if self.cas_failure == "ambiguous_after":
            raise DurableSecretBackendAmbiguousWrite(OLD_REFRESH)
        result = deepcopy(self.rows[key])
        if self.mutate_readback:
            result["refresh_generation"] = result["refresh_generation"] + 1
        return result


class FakeExchange:
    def exchange(self, binding, *, refresh_secret, attempt_id, minimum_ttl_seconds):
        if refresh_secret != OLD_REFRESH:
            raise AssertionError("unexpected refresh secret")
        return RefreshExchangeResult(
            AccessCredentialGrant(
                binding.provider_id,
                binding.account_id,
                binding.capabilities,
                ACCESS,
                NOW,
                NOW + 900,
            ),
            NEW_REFRESH,
        )


def ready_record() -> RefreshSecretRecord:
    return RefreshSecretRecord(
        binding=BINDING,
        version=0,
        state="ready",
        refresh_secret=OLD_REFRESH,
    )


class DurableSecretStoreTest(unittest.TestCase):
    def setUp(self):
        self.backend = FakeDurableBackend()
        self.store = DurableVersionedSecretStore(self.backend)
        self.key = self.store.key_for(BINDING)
        self.backend.seed(self.key, ready_record())

    def test_binding_key_is_stable_hash_not_raw_identity(self):
        first = self.store.key_for(BINDING)
        second = self.store.key_for(BINDING)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("refresh-secret-v1:"))
        self.assertNotIn(BINDING.provider_id, first)
        self.assertNotIn(BINDING.account_id, first)
        self.assertNotIn(BINDING.capabilities[0], first)

    def test_repr_and_returned_record_do_not_expose_secret_in_adapter_metadata(self):
        rendered = repr(self.store)
        self.assertNotIn(OLD_REFRESH, rendered)
        self.assertIn("<redacted>", rendered)
        record = self.store.read(BINDING)
        self.assertEqual(record.refresh_secret, OLD_REFRESH)
        self.assertNotIn(OLD_REFRESH, repr(record))

    def test_read_rejects_corrupt_record_with_fixed_error(self):
        self.backend.rows[self.key]["schema_version"] = "wrong"
        self.backend.rows[self.key]["debug"] = OLD_REFRESH
        with self.assertRaisesRegex(SecretStoreError, "secret_store_record_invalid") as caught:
            self.store.read(BINDING)
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(OLD_REFRESH, str(caught.exception))

    def test_read_backend_failure_is_redacted_and_context_free(self):
        for mode in ("unavailable", "unexpected"):
            with self.subTest(mode=mode):
                self.backend.read_failure = mode
                with self.assertRaisesRegex(SecretStoreError, "secret_store_backend_unavailable") as caught:
                    self.store.read(BINDING)
                self.assertIsNone(caught.exception.__context__)
                self.assertNotIn(OLD_REFRESH, str(caught.exception))
                self.backend.read_failure = None

    def test_cas_conflict_and_ambiguous_write_have_fixed_errors(self):
        replacement = RefreshSecretRecord(
            binding=BINDING,
            version=1,
            state="refreshing",
            refresh_secret=OLD_REFRESH,
            active_attempt_id="attempt-1",
        )
        for mode, expected_error, expected_text in (
            ("conflict", SecretStoreConflict, "secret_store_version_conflict"),
            ("ambiguous_before", SecretStoreAmbiguousWrite, "secret_store_write_ambiguous"),
        ):
            with self.subTest(mode=mode):
                self.backend.cas_failure = mode
                with self.assertRaises(expected_error) as caught:
                    self.store.compare_and_swap(
                        BINDING,
                        expected_version=0,
                        replacement=replacement,
                    )
                self.assertEqual(str(caught.exception), expected_text)
                self.assertIsNone(caught.exception.__context__)
                self.backend.cas_failure = None

    def test_unexpected_cas_backend_error_is_redacted(self):
        replacement = RefreshSecretRecord(
            binding=BINDING,
            version=1,
            state="refreshing",
            refresh_secret=OLD_REFRESH,
            active_attempt_id="attempt-1",
        )
        self.backend.cas_failure = "unexpected"
        with self.assertRaisesRegex(SecretStoreError, "secret_store_backend_unavailable") as caught:
            self.store.compare_and_swap(BINDING, expected_version=0, replacement=replacement)
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(OLD_REFRESH, str(caught.exception))

    def test_cas_requires_exact_backend_readback(self):
        replacement = RefreshSecretRecord(
            binding=BINDING,
            version=1,
            state="refreshing",
            refresh_secret=OLD_REFRESH,
            active_attempt_id="attempt-1",
        )
        self.backend.mutate_readback = True
        with self.assertRaisesRegex(SecretStoreError, "secret_store_cas_readback_mismatch"):
            self.store.compare_and_swap(BINDING, expected_version=0, replacement=replacement)

    def test_missing_record_is_fixed_unconfigured_auth_block(self):
        other = CredentialBinding("fixture-provider", "other-account", ("repository.read",))
        with self.assertRaisesRegex(CredentialAuthBlocked, "credential_secret_unconfigured"):
            self.store.read(other)

    def test_adapter_composes_with_versioned_source_successfully(self):
        source = VersionedHostCredentialSource(
            BINDING,
            self.store,
            FakeExchange(),
            attempt_id_factory=lambda: "attempt-durable",
        )
        grant = source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(grant.access_token, ACCESS)
        final = self.store.read(BINDING)
        self.assertEqual(final.state, "ready")
        self.assertEqual(final.version, 2)
        self.assertEqual(final.refresh_generation, 1)
        self.assertEqual(final.refresh_secret, NEW_REFRESH)

    def test_ambiguous_after_apply_is_resolved_by_source_readback(self):
        source = VersionedHostCredentialSource(
            BINDING,
            self.store,
            FakeExchange(),
            attempt_id_factory=lambda: "attempt-durable",
        )
        self.backend.cas_failure = "ambiguous_after"
        # The first CAS applies then reports ambiguity. Source readback confirms exact
        # ownership and proceeds. Disable later faults after first observed write.
        original = self.backend.compare_and_swap
        calls = 0

        def one_fault(key, *, expected_version, replacement):
            nonlocal calls
            calls += 1
            if calls == 1:
                self.backend.cas_failure = "ambiguous_after"
                try:
                    return original(key, expected_version=expected_version, replacement=replacement)
                finally:
                    self.backend.cas_failure = None
            return original(key, expected_version=expected_version, replacement=replacement)

        self.backend.compare_and_swap = one_fault
        grant = source.refresh_access(BINDING, minimum_ttl_seconds=300)
        self.assertEqual(grant.access_token, ACCESS)
        self.assertEqual(self.store.read(BINDING).refresh_secret, NEW_REFRESH)

    def test_backend_payload_schema_is_explicit_and_secret_is_host_only(self):
        raw = self.backend.rows[self.key]
        self.assertEqual(raw["schema_version"], SECRET_RECORD_SCHEMA_VERSION)
        self.assertEqual(raw["refresh_secret"], OLD_REFRESH)
        # Safe application-facing metadata still comes from RefreshSecretRecord, not
        # the secret-bearing backend payload.
        safe = self.store.read(BINDING).to_safe_dict()
        self.assertNotIn("refresh_secret", safe)
        self.assertEqual(safe["refresh_secret_present"], True)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import traceback
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import (
    AgentRunner, CredentialLifetimeError, CredentialProvider,
    CredentialProviderError, CredentialRevokedError, CredentialScopeError,
    CredentialSnapshot, FileStateStore, StaticInMemoryCredentialProvider,
    StepSpec, TaskSpec,
)

NOW = 1_800_000_000
SECRET = 'access-secret-fixture-never-persist'
CAPABILITY = 'github.read'


def provider(**overrides):
    options = dict(provider_id='github', account_label='owner-fixture',
                   capabilities=(CAPABILITY,), secrets={'access_token': SECRET},
                   issued_at=NOW - 60, expires_at=NOW + 600)
    options.update(overrides)
    return StaticInMemoryCredentialProvider(**options)


def snapshot(source=None, **overrides):
    options = dict(now_epoch=NOW, minimum_ttl_seconds=300)
    options.update(overrides)
    return (source or provider()).snapshot((CAPABILITY,), **options)


class CredentialProviderTest(unittest.TestCase):
    def test_secret_values_absent_from_repr_and_safe_dict(self):
        source: CredentialProvider = provider()
        view = snapshot(source)
        self.assertIsInstance(view, CredentialSnapshot)
        rendered = repr(source) + repr(view) + json.dumps(view.to_safe_dict())
        self.assertNotIn(SECRET, rendered)
        self.assertIn('<redacted>', repr(view))
        self.assertEqual(view.secret('access_token'), SECRET)

    def test_scope_mismatch_fails_closed(self):
        for required in [('github.write',), (CAPABILITY, 'github.write')]:
            with self.subTest(required=required), self.assertRaises(CredentialScopeError):
                provider().snapshot(required, now_epoch=NOW)

    def test_expired_credentials_rejected_even_with_zero_minimum(self):
        for expiry in (NOW - 1, NOW):
            with self.subTest(expiry=expiry), self.assertRaisesRegex(CredentialLifetimeError, 'credential_expired'):
                snapshot(provider(expires_at=expiry), minimum_ttl_seconds=0)

    def test_insufficient_ttl_rejected_and_exact_boundary_accepted(self):
        with self.assertRaisesRegex(CredentialLifetimeError, 'ttl_below_minimum'):
            snapshot(provider(expires_at=NOW + 299))
        self.assertEqual(snapshot(provider(expires_at=NOW + 300)).expires_at, NOW + 300)

    def test_expiry_rechecked_on_every_snapshot(self):
        source = provider()
        snapshot(source)
        with self.assertRaises(CredentialLifetimeError):
            snapshot(source, now_epoch=NOW + 301)
        with self.assertRaisesRegex(CredentialLifetimeError, 'credential_expired'):
            snapshot(source, now_epoch=NOW + 600, minimum_ttl_seconds=0)

    def test_unknown_expiry_is_explicit_and_can_be_required(self):
        source = provider(expires_at=None)
        view = snapshot(source)
        self.assertIsNone(view.expires_at)
        self.assertIsNone(view.to_safe_dict()['expires_in_seconds_at_snapshot'])
        with self.assertRaisesRegex(CredentialLifetimeError, 'expiry_unknown'):
            snapshot(source, require_known_expiry=True)

    def test_static_provider_is_not_refresh_capable(self):
        source = provider()
        self.assertIs(source.refresh_capable, False)
        self.assertIs(snapshot(source).refresh_capable, False)
        self.assertFalse(hasattr(source, 'refresh'))

    def test_revocation_prevents_all_new_snapshots(self):
        source = provider()
        old_view = snapshot(source)
        source.revoke()
        source.revoke()
        for options in ({}, {'minimum_ttl_seconds': 0}, {'require_known_expiry': False}):
            with self.assertRaises(CredentialRevokedError):
                snapshot(source, **options)
        # Revocation is a local issuance boundary, not remote token invalidation.
        self.assertEqual(old_view.secret('access_token'), SECRET)

    def test_secret_names_and_identity_metadata_are_available(self):
        view = snapshot(provider(provider_id=' github ', account_label=' owner-fixture ',
                                 secrets={'access_token': SECRET, 'api_key': 'key-fixture'}))
        self.assertEqual(view.provider_id, 'github')
        self.assertEqual(view.account_label, 'owner-fixture')
        self.assertEqual(view.capabilities, (CAPABILITY,))
        self.assertEqual(view.issued_at, NOW - 60)
        self.assertEqual(view.secret_names, ('access_token', 'api_key'))
        report = view.to_safe_dict()
        self.assertEqual(report['provider_id'], view.provider_id)
        self.assertEqual(report['account_label'], view.account_label)
        self.assertEqual(report['secret_names'], list(view.secret_names))
        self.assertEqual(report['expires_in_seconds_at_snapshot'], 600)
        self.assertIsNone(snapshot(provider(account_label=None)).account_label)

    def test_caller_mutation_does_not_rotate_credentials_or_scopes(self):
        values = {'access_token': SECRET}
        caps = [CAPABILITY]
        source = provider(secrets=values, capabilities=caps)
        values['access_token'] = 'mutated-fixture'
        caps.append('github.write')
        view = snapshot(source)
        report = view.to_safe_dict()
        report['capabilities'].append('github.write')
        report['secret_names'].clear()
        self.assertEqual(view.secret('access_token'), SECRET)
        self.assertEqual(view.capabilities, (CAPABILITY,))
        self.assertEqual(view.secret_names, ('access_token',))
        with self.assertRaises(CredentialScopeError):
            source.snapshot(('github.write',), now_epoch=NOW)

    def test_missing_secret_errors_never_echo_lookup_or_traceback_cause(self):
        view = snapshot()
        try:
            view.secret(SECRET)
        except CredentialProviderError as error:
            rendered = ''.join(traceback.format_exception(error))
            self.assertNotIn(SECRET, str(error))
            self.assertNotIn(SECRET, rendered)
            self.assertIsNone(error.__cause__)
        else:
            self.fail('Missing secret must fail closed')

    def test_scope_error_never_echoes_untrusted_input(self):
        with self.assertRaises(CredentialScopeError) as caught:
            provider().snapshot((SECRET,), now_epoch=NOW)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_malformed_ttl_is_rejected(self):
        for ttl in (-1, True, False, 0.5, float('nan'), float('inf'), '300', None):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                snapshot(minimum_ttl_seconds=ttl)

    def test_malformed_epoch_values_are_rejected_without_coercion(self):
        for value in (-1, True, 1.5, float('nan'), '1800000000'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    snapshot(now_epoch=value)
                for field in ('issued_at', 'expires_at'):
                    with self.assertRaises(ValueError):
                        provider(**{field: value})

    def test_issue_time_cannot_follow_expiry_or_snapshot_time(self):
        with self.assertRaisesRegex(ValueError, 'expiry_must_follow'):
            provider(issued_at=NOW, expires_at=NOW)
        with self.assertRaisesRegex(CredentialLifetimeError, 'not_yet_valid'):
            snapshot(provider(issued_at=NOW + 1))

    def test_default_clock_and_required_expiry_boolean(self):
        with patch('agent_core.credential_provider.time.time', return_value=NOW):
            self.assertEqual(provider().snapshot((CAPABILITY,)).expires_at, NOW + 600)
        for value in (None, 0, 'false'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                snapshot(require_known_expiry=value)

    def test_invalid_capability_collections_fail_closed(self):
        for value in ((), [''], [' '], [None], [CAPABILITY, ''], CAPABILITY, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider(capabilities=value)
                with self.assertRaises(ValueError):
                    provider().snapshot(value, now_epoch=NOW)

    def test_invalid_secrets_are_not_stringified_into_credentials(self):
        for values in ({}, {'': SECRET}, {'access_token': None}, {'access_token': 123},
                       {'access_token': ''}, {'access_token': ' '}, {None: SECRET}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                provider(secrets=values)

    def test_rotation_preserves_task_identity_persistence_and_no_replay(self):
        spec = TaskSpec('credential-rotation', 'Rotation test', 'Runtime-only access',
                        (CAPABILITY,), (StepSpec('read', CAPABILITY),))
        encoded = json.dumps(spec.to_dict(), sort_keys=True)
        fingerprint = spec.fingerprint()
        first = provider()
        second_secret = 'rotated-access-fixture-never-persist'
        second = provider(secrets={'access_token': second_secret}, expires_at=NOW + 900)
        seen = []
        def adapter(source):
            def read(args, context):
                view = snapshot(source)
                seen.append(view.secret('access_token'))
                return {'authenticated': True}
            return read
        with TemporaryDirectory() as tmp:
            state_store = FileStateStore(tmp)
            self.assertEqual(AgentRunner(state_store, {CAPABILITY: adapter(first)}).run(spec).status, 'completed')
            first.revoke()
            self.assertEqual(snapshot(second).secret('access_token'), second_secret)
            self.assertEqual(AgentRunner(state_store, {CAPABILITY: adapter(second)}).run(spec).status, 'completed')
            self.assertEqual(seen, [SECRET])  # Credential rotation cannot replay completed work.
            self.assertEqual(spec.fingerprint(), fingerprint)
            self.assertEqual(json.dumps(spec.to_dict(), sort_keys=True), encoded)
            self.assertEqual(state_store.load_state(spec.task_id).spec_fingerprint, fingerprint)
            persisted = ''.join(p.read_text() for p in Path(tmp).rglob('*') if p.is_file())
            for secret in (SECRET, second_secret):
                self.assertNotIn(secret, persisted + encoded)


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import traceback
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import (
    AccessCredentialGrant, AgentRunner, CredentialAuthBlocked, CredentialBinding,
    CredentialRefreshInProgress, CredentialRevokedError, CredentialScopeError,
    FileStateStore, RefreshingCredentialProvider, StepSpec, TaskSpec,
)

NOW = 1_800_000_000
BINDING = CredentialBinding('fixture-provider', 'fixture-owner', ('repository.read',))
ACCESS = 'access-fixture-secret'
REFRESH = 'host-only-refresh-fixture-secret'


def grant(**changes):
    return replace(AccessCredentialGrant(BINDING.provider_id, BINDING.account_id,
                   BINDING.capabilities, ACCESS, NOW - 10, NOW + 600), **changes)


class FakeHostSource:
    """No network or real secret store: simulate the host-only contract."""
    def __init__(self):
        self.calls = 0
        self.checks = 0
        self.enabled = True
        self.result = grant()
        self.callback = None
        self.refresh_secret = REFRESH

    def assert_available(self):
        self.checks += 1
        if not self.enabled:
            raise CredentialRevokedError(REFRESH)

    def refresh_access(self, binding, *, minimum_ttl_seconds):
        self.calls += 1
        assert binding == BINDING
        if self.callback:
            return self.callback()
        return self.result


class RefreshCredentialsTest(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.source = FakeHostSource()
        self.provider = RefreshingCredentialProvider(BINDING, self.source, clock=lambda: self.now)

    def snapshot(self, **kwargs):
        return self.provider.snapshot(BINDING.capabilities, **kwargs)

    def state(self):
        return self.provider.to_safe_dict()['state']

    def test_initial_refresh_returns_only_access_and_enters_ready(self):
        self.assertEqual(self.state(), 'refresh_required')
        result = self.snapshot()
        self.assertEqual(self.state(), 'ready')
        self.assertEqual(self.source.calls, 1)
        self.assertEqual(result.secret_names, ('access_token',))
        self.assertEqual(result.secret('access_token'), ACCESS)
        self.assertEqual(result.provider_id, BINDING.provider_id)
        self.assertEqual(result.account_label, BINDING.account_id)
        self.assertTrue(result.refresh_capable)
        self.assertFalse(hasattr(result, 'refresh_access'))
        self.assertFalse(hasattr(result, 'refresh_secret'))

    def test_cached_access_checks_source_but_does_not_refresh(self):
        first = self.snapshot()
        self.now += 300
        second = self.snapshot()
        self.assertIsNot(first, second)
        self.assertEqual(self.source.calls, 1)
        self.assertEqual(self.source.checks, 4)
        self.assertEqual(second.to_safe_dict()['expires_in_seconds_at_snapshot'], 300)

    def test_low_ttl_refreshes_and_rotates_once(self):
        self.snapshot()
        self.now += 301
        self.source.result = grant(access_token='rotated-access-fixture', issued_at=self.now,
                                   expires_at=self.now + 600)
        view = self.snapshot()
        self.assertEqual(view.secret('access_token'), 'rotated-access-fixture')
        self.assertEqual(self.source.calls, 2)
        self.assertEqual(self.state(), 'ready_rotated')
        self.assertEqual(self.provider.to_safe_dict()['generation'], 2)

    def test_expired_cache_with_zero_ttl_still_refreshes(self):
        self.snapshot()
        self.now += 600
        self.source.result = grant(issued_at=self.now, expires_at=self.now + 600)
        self.snapshot(minimum_ttl_seconds=0)
        self.assertEqual(self.source.calls, 2)

    def test_invalid_response_blocks_auth_and_cannot_fall_back_or_retry(self):
        variants = [grant(provider_id='other'), grant(account_id='other'),
                    grant(capabilities=('repository.read', 'repository.write')),
                    grant(capabilities=()), grant(capabilities=('other',)),
                    grant(access_token=''), grant(access_token=None), grant(issued_at=NOW+1),
                    grant(expires_at=None), grant(expires_at=NOW), grant(expires_at=NOW+299),
                    grant(expires_at=True), grant(expires_at=float('nan')),
                    {'access_token': ACCESS, 'refresh_token': REFRESH}]
        for result in variants:
            with self.subTest(result=result):
                source = FakeHostSource()
                source.result = result
                provider = RefreshingCredentialProvider(BINDING, source, clock=lambda: NOW)
                with self.assertRaises(CredentialAuthBlocked):
                    provider.snapshot(BINDING.capabilities)
                self.assertEqual(provider.to_safe_dict()['state'], 'blocked_auth')
                source.result = grant()
                with self.assertRaises(CredentialAuthBlocked):
                    provider.snapshot(BINDING.capabilities)
                self.assertEqual(source.calls, 1)

    def test_failure_after_previous_success_discards_cache(self):
        self.snapshot()
        self.now += 301
        self.source.callback = lambda: (_ for _ in ()).throw(RuntimeError(REFRESH))
        with self.assertRaises(CredentialAuthBlocked):
            self.snapshot()
        self.assertIsNone(self.provider.to_safe_dict()['expires_at'])
        with self.assertRaises(CredentialAuthBlocked):
            self.snapshot(minimum_ttl_seconds=0)
        self.assertEqual(self.source.calls, 2)

    def test_all_reports_reprs_and_failure_tracebacks_are_redacted(self):
        view = self.snapshot()
        reports = repr(view) + repr(self.provider) + repr(self.source.result)
        reports += json.dumps(view.to_safe_dict()) + json.dumps(self.provider.to_safe_dict())
        for secret in (ACCESS, REFRESH):
            self.assertNotIn(secret, reports)
        self.now += 301
        self.source.callback = lambda: (_ for _ in ()).throw(RuntimeError(REFRESH + ACCESS))
        try:
            self.snapshot()
        except CredentialAuthBlocked as error:
            rendered = ''.join(traceback.format_exception(error))
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
            for secret in (ACCESS, REFRESH):
                self.assertNotIn(secret, rendered + repr(self.provider))
        else:
            self.fail('Refresh failure must block authentication')

    def test_untrusted_response_identity_is_never_reported(self):
        self.source.result = grant(provider_id=REFRESH, account_id=ACCESS)
        with self.assertRaises(CredentialAuthBlocked):
            self.snapshot()
        self.assertNotIn(REFRESH, repr(self.provider))
        self.assertNotIn(ACCESS, repr(self.provider))
        self.assertNotIn(REFRESH, repr(self.source.result))

    def test_requested_scope_mismatch_never_calls_source(self):
        with self.assertRaises(CredentialScopeError):
            self.provider.snapshot(('repository.write',))
        self.assertEqual(self.source.calls, 0)
        self.assertEqual(self.source.checks, 0)
        self.assertEqual(self.state(), 'refresh_required')

    def test_malformed_request_never_calls_source(self):
        for value in (-1, True, 0.5, float('nan'), '300'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.snapshot(minimum_ttl_seconds=value)
        for value in (None, [], [''], 'repository.read'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.provider.snapshot(value)
        with self.assertRaises(ValueError):
            self.snapshot(require_known_expiry='false')
        with self.assertRaises(ValueError):
            self.snapshot(now_epoch=True)
        self.assertEqual(self.source.checks, 0)

    def test_unknown_expiry_is_always_rejected(self):
        self.source.result = grant(expires_at=None)
        with self.assertRaises(CredentialAuthBlocked):
            self.snapshot(require_known_expiry=False)

    def test_local_revocation_is_terminal(self):
        self.snapshot()
        self.provider.revoke()
        self.provider.revoke()
        with self.assertRaises(CredentialRevokedError):
            self.snapshot()
        self.assertEqual(self.state(), 'revoked')
        self.assertIsNone(self.provider.to_safe_dict()['expires_at'])
        self.assertEqual(self.source.calls, 1)

    def test_source_revocation_invalidates_cached_issuance(self):
        self.snapshot()
        self.source.enabled = False
        with self.assertRaises(CredentialRevokedError):
            self.snapshot()
        self.assertEqual(self.state(), 'revoked')
        self.source.enabled = True
        with self.assertRaises(CredentialRevokedError):
            self.snapshot()
        self.assertEqual(self.source.calls, 1)

    def test_source_revocation_during_refresh_discards_returned_access(self):
        def refresh():
            self.source.enabled = False
            return grant()
        self.source.callback = refresh
        with self.assertRaises(CredentialRevokedError):
            self.snapshot()
        self.assertEqual(self.provider.to_safe_dict()['generation'], 0)
        self.assertEqual(self.state(), 'revoked')

    def test_time_is_rechecked_after_slow_refresh(self):
        def slow_refresh():
            self.now += 301
            return grant()
        self.source.callback = slow_refresh
        with self.assertRaises(CredentialAuthBlocked):
            self.snapshot()
        self.assertEqual(self.state(), 'blocked_auth')

    def test_monotonic_time_prevents_clock_rollback_during_refresh(self):
        monotonic = [100]
        def slow_refresh():
            monotonic[0] += 301
            self.now -= 300
            return grant()
        self.source.callback = slow_refresh
        with patch('agent_core.refresh_credentials.time.monotonic', side_effect=lambda: monotonic[0]):
            with self.assertRaises(CredentialAuthBlocked):
                self.snapshot()
        self.assertEqual(self.state(), 'blocked_auth')

    def test_concurrent_caller_cannot_start_second_refresh(self):
        entered, release = Event(), Event()
        results, errors = [], []
        def slow_refresh():
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test_timeout')
            return grant()
        self.source.callback = slow_refresh
        def issue():
            try:
                results.append(self.snapshot())
            except BaseException as error:
                errors.append(error)
        thread = Thread(target=issue)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.state(), 'refreshing')
            with self.assertRaises(CredentialRefreshInProgress):
                self.snapshot()
            self.assertEqual(self.source.calls, 1)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(self.state(), 'ready')

    def test_revoke_wins_over_inflight_refresh(self):
        entered, release = Event(), Event()
        errors = []
        def slow_refresh():
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test_timeout')
            return grant()
        self.source.callback = slow_refresh
        def issue():
            try:
                self.snapshot()
            except BaseException as error:
                errors.append(error)
        thread = Thread(target=issue)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.provider.revoke()
            self.assertEqual(self.state(), 'revoked')
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], CredentialRevokedError)
        self.assertEqual(self.provider.to_safe_dict()['generation'], 0)

    def test_interruption_blocks_future_refresh_without_leaking_error(self):
        for kind in (KeyboardInterrupt, SystemExit):
            with self.subTest(kind=kind):
                source = FakeHostSource()
                source.callback = lambda: (_ for _ in ()).throw(kind(REFRESH))
                provider = RefreshingCredentialProvider(BINDING, source, clock=lambda: NOW)
                with self.assertRaises(kind) as caught:
                    provider.snapshot(BINDING.capabilities)
                self.assertNotIn(REFRESH, str(caught.exception))
                self.assertEqual(provider.to_safe_dict()['state'], 'blocked_auth')
                with self.assertRaises(CredentialAuthBlocked):
                    provider.snapshot(BINDING.capabilities)
                self.assertEqual(source.calls, 1)

    def test_unconfigured_source_has_no_snapshot(self):
        provider = RefreshingCredentialProvider(BINDING, None)
        self.assertEqual(provider.to_safe_dict()['state'], 'unconfigured')
        with self.assertRaises(CredentialAuthBlocked):
            provider.snapshot(BINDING.capabilities)

    def test_clock_rollback_between_snapshots_cannot_extend_cached_ttl(self):
        monotonic = [100]
        with patch('agent_core.refresh_credentials.time.monotonic', side_effect=lambda: monotonic[0]):
            self.snapshot()
            monotonic[0] += 301
            self.now -= 300
            self.source.result = grant(issued_at=NOW + 301, expires_at=NOW + 1200)
            result = self.snapshot()
        self.assertEqual(self.source.calls, 2)
        self.assertEqual(result.to_safe_dict()['expires_in_seconds_at_snapshot'], 899)

    def test_frequent_snapshots_do_not_lose_fractional_elapsed_time(self):
        monotonic = [100.0]
        with patch('agent_core.refresh_credentials.time.monotonic', side_effect=lambda: monotonic[0]):
            self.snapshot()
            self.now -= 300
            for _ in range(8):
                monotonic[0] += 0.25
                result = self.snapshot()
        self.assertEqual(result.to_safe_dict()['expires_in_seconds_at_snapshot'], 598)
        self.assertEqual(self.source.calls, 1)

    def test_availability_failure_blocks_before_refresh_and_never_echoes_source(self):
        def failure():
            raise RuntimeError(REFRESH)
        self.source.assert_available = failure
        with self.assertRaises(CredentialAuthBlocked) as caught:
            self.snapshot()
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(self.source.calls, 0)
        self.assertEqual(self.state(), 'blocked_auth')
        self.assertNotIn(REFRESH, repr(self.provider))

    def test_safe_report_cannot_mutate_binding(self):
        report = self.provider.to_safe_dict()
        report['capabilities'].append('repository.write')
        report['state'] = 'ready'
        self.assertEqual(self.state(), 'refresh_required')
        self.assertEqual(self.provider.to_safe_dict()['capabilities'], list(BINDING.capabilities))
        with self.assertRaises(CredentialScopeError):
            self.provider.snapshot(('repository.write',))

    def test_invalid_binding_is_rejected(self):
        for identity in ('', ' ', ' owner ', None):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                CredentialBinding('fixture-provider', identity, BINDING.capabilities)
        with self.assertRaises(ValueError):
            RefreshingCredentialProvider(None, self.source)

    def test_rotation_preserves_task_fingerprint_state_and_no_replay(self):
        spec = TaskSpec('refresh-rotation', 'Refresh fixture', 'Access-only adapter',
                        BINDING.capabilities, (StepSpec('read', BINDING.capabilities[0]),))
        fingerprint = spec.fingerprint()
        calls = []
        def action(args, context):
            view = self.snapshot()
            calls.append(view.secret('access_token'))
            return {'authenticated': True}
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            runner = AgentRunner(store, {BINDING.capabilities[0]: action})
            self.assertEqual(runner.run(spec).status, 'completed')
            self.now += 301
            self.source.result = grant(access_token='new-access-fixture', issued_at=self.now,
                                       expires_at=self.now + 600)
            self.snapshot()
            self.assertEqual(runner.run(spec).status, 'completed')
            self.assertEqual(calls, [ACCESS])
            self.assertEqual(spec.fingerprint(), fingerprint)
            self.assertEqual(store.load_state(spec.task_id).spec_fingerprint, fingerprint)
            persisted = ''.join(p.read_text() for p in Path(tmp).rglob('*') if p.is_file())
            for secret in (ACCESS, REFRESH, 'new-access-fixture'):
                self.assertNotIn(secret, persisted + json.dumps(spec.to_dict()))


if __name__ == '__main__':
    unittest.main()

"""Synthetic race identities across expiration, v1 migration and failed saves."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.model_history import capture_prediction
from ml.synthetic_session import (SCHEMA, LEGACY_SCHEMA, JST, FILENAME,
                                  SessionStore, SessionSaveError, validate_session)
from ml.synthetic_workbench import Workbench
from test_model_history import prediction, NOW
from test_synthetic_workbench_session import saved_session
from test_synthetic_workbench_session_transfer import transfer


@contextmanager
def generated_at(app, now):
    """Keep inference fixed while exercising real capture, persistence and review."""
    def predict(data, _models):
        result = prediction(len(data['players']))
        result['race'] = deepcopy(data['race'])
        result['generated_at'] = (now - timedelta(seconds=1)).isoformat()
        return result
    with patch.object(app, '_train'), \
            patch('ml.predict_position_models.predict_race', side_effect=predict), \
            patch('ml.synthetic_workbench.datetime', wraps=datetime) as clock, \
            patch('ml.model_history.datetime', wraps=datetime) as capture_clock:
        clock.now.return_value = capture_clock.now.return_value = now
        yield


def legacy_numbered():
    value = saved_session()
    value['series'] = 1
    value['histories'] = {}
    for key, count in [('a'*32, 7), ('b'*32, 9)]:
        p = prediction(count)
        p['race']['race_number'] = 10 + count
        with patch('ml.model_history.datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            value['snapshots'][key] = capture_prediction(p, synthetic=True)
    return value


class RolloverTests(unittest.TestCase):
    def test_repeated_expiration_seven_nine_review_and_restart(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)/'state'
            app = Workbench(directory)
            try:
                # UTC Dec 31 / JST Jan 1; two expirations occur on the same
                # local day as each previous schedule, not just after midnight.
                now = datetime(2026, 12, 31, 14, 30, tzinfo=timezone.utc)
                app._commit(app._payload(scheduled=(now + timedelta(hours=1)).isoformat()))
                identities, days = set(), []
                for generation in range(3):
                    previous = deepcopy(app.snapshots)
                    with generated_at(app, now):
                        for count in (7, 9):
                            state = app.predict(count)
                            key = state['current']['snapshot_id']
                            snap = app.snapshots[key]
                            self.assertEqual(state['current']['race']['race_number'], count)
                            self.assertNotIn(snap['race_id'], identities)
                            identities.add(snap['race_id'])
                            app.hold(key, 'cancelled')
                    self.assertTrue(all(app.snapshots[k] == s for k, s in previous.items()))
                    days.append(app.scheduled.astimezone(JST).date())
                    self.assertEqual(transfer(app)['report']['unresolved_races'], 2*(generation+1))
                    frozen = deepcopy(app._payload())
                    now = app.scheduled + timedelta(minutes=5)
                    app.close(); app = Workbench(directory)
                    self.assertEqual(app._payload(), frozen)
                    self.assertFalse(app.ready)
                self.assertEqual(days[0].isoformat(), '2027-01-01')
                self.assertEqual([days[i+1]-days[i] for i in range(2)], [timedelta(days=1)]*2)
                # Repeated predictions before the same schedule remain one race.
                with generated_at(app, app.scheduled-timedelta(minutes=1)):
                    state = app.predict(7)
                self.assertIn(app.snapshots[state['current']['snapshot_id']]['race_id'], identities)
            finally:
                app.close()

    def test_v1_read_and_old_operations_stay_v1_then_prediction_upgrades(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); initial = saved_session()
            store = SessionStore(directory); store.save(initial); store.close()
            path = directory/FILENAME; original = path.read_bytes(); app = Workbench(directory)
            try:
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(app._payload(), initial)
                with patch.object(app, '_train', side_effect=AssertionError('restore must not train')):
                    app.select('b'*32); app.hold('b'*32, 'cancelled')
                self.assertEqual(app.schema, LEGACY_SCHEMA)
                old = deepcopy(app._payload())
                # Upgrade even before expiry: the new race gets a distinct day.
                with generated_at(app, NOW):
                    app.predict(7)
                self.assertEqual(app.schema, SCHEMA)
                self.assertEqual(app.histories, old['histories'])
                self.assertTrue(all(app.snapshots[k] == s for k, s in old['snapshots'].items()))
                self.assertGreater(app.scheduled.astimezone(JST).date(),
                                   datetime.fromisoformat(old['scheduled']).astimezone(JST).date())
                self.assertEqual(transfer(app)['report']['unresolved_races'], 1)
                frozen = deepcopy(app._payload())
            finally:
                app.close()
            restored = Workbench(directory)
            try:
                self.assertEqual(restored._payload(), frozen)
                self.assertFalse(restored.ready)
            finally:
                restored.close()

    def test_old_17_and_19_are_preserved_and_whole_review_still_refused(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); old = legacy_numbered()
            store = SessionStore(directory); store.save(old); store.close()
            app = Workbench(directory)
            try:
                for key in old['snapshots']: app.hold(key, 'cancelled')
                histories = deepcopy(app.histories)
                with generated_at(app, NOW): app.predict(9)
                app.hold(app.current, 'cancelled')
                self.assertEqual(app.schema, SCHEMA)
                self.assertTrue(all(app.snapshots[k] == s for k, s in old['snapshots'].items()))
                self.assertTrue(all(app.histories[k] == h for k, h in histories.items()))
                frozen = deepcopy(app._payload())
                with self.assertRaisesRegex(ValueError, 'race_number_invalid'): transfer(app)
                self.assertEqual(app._payload(), frozen)
                self.assertEqual(app.held_review.holds, [])
            finally:
                app.close()
            restored = Workbench(directory)
            try: self.assertEqual(restored._payload(), frozen)
            finally: restored.close()

    def test_migration_save_failure_reconciles_without_mutating_old_records(self):
        for after_replace in (False, True):
            with self.subTest(after_replace=after_replace), TemporaryDirectory() as tmp:
                directory = Path(tmp); old = saved_session()
                store = SessionStore(directory); store.save(old); store.close()
                path = directory/FILENAME; original = path.read_bytes(); app = Workbench(directory)
                real_fsync = os.fsync
                def fail(fd):
                    replaced = json.loads(path.read_bytes())['payload']['schema_version'] == SCHEMA
                    if replaced == after_replace: raise OSError('injected migration sync failure')
                    real_fsync(fd)
                try:
                    with generated_at(app, NOW), patch('ml.synthetic_session.os.fsync', side_effect=fail):
                        with self.assertRaises(SessionSaveError): app.predict(9)
                    self.assertEqual(app._payload(), old)
                    self.assertTrue(app.store.failed)
                    if not after_replace: self.assertEqual(path.read_bytes(), original)
                finally:
                    app.close()
                restored = Workbench(directory)
                try:
                    self.assertEqual(restored.schema, SCHEMA if after_replace else LEGACY_SCHEMA)
                    self.assertTrue(all(restored.snapshots[k] == s for k, s in old['snapshots'].items()))
                    self.assertEqual(restored.histories, old['histories'])
                finally: restored.close()

    def test_v2_corruption_schedule_collision_and_legacy_reclassification_refused(self):
        app = Workbench()
        try:
            app._apply(saved_session())
            with generated_at(app, NOW): app.predict(7)
            valid = deepcopy(app._payload()); new_key = app.current
            mutations = [
                lambda p: p.update(series=0),
                lambda p: p['legacy'].update(series=True),
                lambda p: p['legacy']['snapshot_hashes'].update({'c'*32: 'a'*64}),
                lambda p: p['legacy']['snapshot_hashes'].update({'a'*32: '0'*64}),
                lambda p: p['legacy'].update(snapshot_hashes={}),  # Old days cannot become new days.
                lambda p: p.update(scheduled=(datetime.fromisoformat(p['scheduled'])+timedelta(minutes=1)).isoformat()),
                lambda p: p.update(scheduled=(datetime.fromisoformat(p['scheduled'])-timedelta(days=2)).isoformat()),
                lambda p: p.update(schema_version='synthetic-workbench-session-v3'),
            ]
            for mutate in mutations:
                bad = deepcopy(valid); mutate(bad)
                with self.subTest(mutate=mutate), self.assertRaises(ValueError): validate_session(bad)
            # A fully valid snapshot with a legacy-style number is still invalid
            # as a v2-generated record, even with all hashes recomputed.
            bad = deepcopy(valid); p = deepcopy(bad['snapshots'][new_key]['prediction'])
            p['race']['race_number'] = 17
            with patch('ml.model_history.datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                bad['snapshots'][new_key] = capture_prediction(p, synthetic=True)
            with self.assertRaisesRegex(ValueError, 'generated_session_race_required'): validate_session(bad)
            self.assertEqual(app._payload(), valid)
        finally: app.close()

    def test_v1_formula_and_active_schedule_validation_are_not_relaxed(self):
        for mutate in (lambda p: p.update(series=0),
                       lambda p: p.update(scheduled='2026-10-17T03:00:00+00:00')):
            bad = legacy_numbered(); mutate(bad)
            with self.assertRaises(ValueError): validate_session(bad)


if __name__ == '__main__': unittest.main()

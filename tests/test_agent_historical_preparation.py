import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.historical_preparation import TASK_ID, REPOSITORY, HistoricalPreparationAdapter, run_preparation
from agent_core.runner import BlockedAction
from agent_core.store import FileStateStore
from ml.historical_training import digest
from test_historical_training import fixture, review


class HistoricalPreparationAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.records, self.reviews, self.run_dir = (self.root / p for p in ('records.json', 'reviews.json', 'job'))
        self.rows = [fixture(d, 9 if d == 2 else 7) for d in range(1, 5)]
        self.write_records()
        self.reviews.write_text(json.dumps([review(r) for r in self.rows]))

    def write_records(self):
        self.records.write_text(json.dumps({'schema_version': 'historical-review-records-v1',
            'records': self.rows, 'record_hashes': {r['race_id']: digest(r) for r in self.rows}}))

    def run_job(self, **kwargs):
        return run_preparation(self.records, self.reviews, self.run_dir,
                               kwargs.get('validation_start', '2020-01-03T00:00:00+09:00'),
                               '2020-01-04T00:00:00+09:00',
                               reconcile_verified_output=kwargs.get('reconcile_verified_output', False))

    def interrupt_after_output(self):
        original = HistoricalPreparationAdapter.run
        def crash(adapter, args, context):
            original(adapter, args, context)
            raise KeyboardInterrupt()
        with patch.object(HistoricalPreparationAdapter, 'run', crash):
            with self.assertRaises(KeyboardInterrupt):
                self.run_job()
        self.assertEqual(self.run_job()['outcome']['status'], 'blocked')

    def test_synthetic_reviewed_partitions_are_prepared_but_never_trained(self):
        with patch('ml.historical_training.train', side_effect=AssertionError('must not train')):
            receipt = self.run_job()
        self.assertEqual(receipt['partition_counts'], {'train': 2, 'validation': 1, 'test': 1})
        self.assertEqual(receipt['outcome']['status'], 'completed')
        self.assertEqual(receipt['training_runs'], 0)
        self.assertFalse(receipt['durable_storage_verified'])
        ledger = (self.run_dir/'state/activity.jsonl').read_text()
        self.assertNotIn('synthetic test evidence', ledger)
        self.assertNotIn('race_score', ledger)

    def test_unapproved_realistic_inputs_complete_diagnostic_with_zero_eligibility(self):
        for r in self.rows:
            r.update(training_use_status='unconfirmed', pre_race_state_verified=False, feature_as_of=None)
        self.write_records()
        self.reviews.write_text('[]')
        receipt = self.run_job()
        self.assertEqual(receipt['outcome']['status'], 'completed')
        self.assertEqual(sum(receipt['partition_counts'].values()), 0)
        self.assertEqual(receipt['excluded_records'], 4)

    def test_resume_does_not_repeat_action_and_preserves_report_bytes_and_mtime(self):
        self.run_job()
        output = self.run_dir/'preparation.json'
        before = (output.read_bytes(), output.stat().st_mtime_ns)
        with patch.object(HistoricalPreparationAdapter, 'run', side_effect=AssertionError('replayed')):
            receipt = self.run_job()
        self.assertEqual(receipt['outcome']['executed_steps'], ())
        self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)

    def test_changed_input_review_or_boundary_cannot_reuse_completed_task(self):
        for change in ('input', 'review', 'boundary'):
            with self.subTest(change=change):
                self.run_dir = self.root / ('job-' + change)
                self.run_job()
                before = (self.run_dir/'preparation.json').read_bytes()
                if change == 'input':
                    self.rows[0]['pre_race_features'][0]['race_score'] += 1
                    self.write_records()
                if change == 'review': self.reviews.write_text('[]')
                with self.assertRaisesRegex(BlockedAction, 'output_conflict'):
                    self.run_job(**({'validation_start': '2020-01-02T00:00:00+09:00'} if change == 'boundary' else {}))
                self.assertEqual((self.run_dir/'preparation.json').read_bytes(), before)

    def test_completed_output_tampering_is_detected_without_rewriting(self):
        self.run_job()
        output = self.run_dir/'preparation.json'
        output.write_text('{"fabricated":true}')
        with self.assertRaisesRegex(BlockedAction, 'readback_mismatch'): self.run_job()
        self.assertEqual(output.read_text(), '{"fabricated":true}')

    def test_record_digest_mismatch_fails_before_creating_task(self):
        data = json.loads(self.records.read_text())
        data['records'][0]['pre_race_features'][0]['race_score'] = 999
        self.records.write_text(json.dumps(data))
        with self.assertRaisesRegex(BlockedAction, 'hashes_mismatch'): self.run_job()
        self.assertFalse(self.run_dir.exists())

    def test_interruption_requires_reconciliation_and_does_not_replay(self):
        self.run_job()
        store = FileStateStore(self.run_dir/'state')
        state = store.load_state(TASK_ID)
        state.status, state.completed_steps = 'running', []
        store.save_state(state)
        with patch.object(HistoricalPreparationAdapter, 'run', side_effect=AssertionError('replayed')):
            receipt = self.run_job()
        self.assertEqual(receipt['outcome']['status'], 'blocked')
        self.assertIn('interrupted_step_requires_reconciliation', receipt['outcome']['blocked_reason'])

    def test_existing_conflicting_output_is_preserved_and_error_text_is_not_logged(self):
        self.run_dir.mkdir()
        output = self.run_dir/'preparation.json'
        output.write_text('private-existing-text')
        first = self.run_job()
        second = self.run_job()
        self.assertEqual(first['outcome']['status'], 'blocked')
        self.assertEqual(second['outcome']['executed_steps'], ())
        self.assertEqual(output.read_text(), 'private-existing-text')
        self.assertNotIn('private-existing-text', (self.run_dir/'state/activity.jsonl').read_text())

    def test_explicit_reconciliation_recovers_crash_after_output_without_replay(self):
        self.interrupt_after_output()
        output = self.run_dir/'preparation.json'
        before = (output.read_bytes(), output.stat().st_mtime_ns)
        store = FileStateStore(self.run_dir/'state')
        self.assertEqual(store.load_state(TASK_ID).artifacts, {})
        with patch.object(HistoricalPreparationAdapter, 'run', side_effect=AssertionError('replayed')):
            recovered = self.run_job(reconcile_verified_output=True)
            again = self.run_job(reconcile_verified_output=True)
        self.assertEqual(recovered['outcome']['status'], 'completed')
        self.assertEqual(recovered['outcome']['executed_steps'], ())
        self.assertEqual(again['outcome']['executed_steps'], ())
        self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)
        state = store.load_state(TASK_ID)
        self.assertEqual(len(state.reconciliations), 1)
        self.assertEqual(state.attempts, {'prepare': 1})
        artifact = state.artifacts['historical-preparation-plan']
        self.assertEqual(artifact.metadata['sha256'], recovered['preparation_sha256'])
        self.assertFalse(artifact.persistent_saved)
        self.assertEqual(recovered['training_runs'], 0)

    def test_reconciliation_missing_tampered_and_symlink_output_preserves_block(self):
        for case in ('missing', 'tampered', 'symlink'):
            with self.subTest(case=case):
                self.run_dir = self.root/('job-'+case)
                self.interrupt_after_output()
                output = self.run_dir/'preparation.json'
                if case == 'missing': output.unlink()
                elif case == 'tampered': output.write_text('private-corruption')
                else:
                    target = self.root/'copy.json'
                    output.rename(target)
                    output.symlink_to(target)
                store = FileStateStore(self.run_dir/'state')
                before = store.state_path(TASK_ID).read_bytes()
                with self.assertRaises((BlockedAction, FileNotFoundError)):
                    self.run_job(reconcile_verified_output=True)
                self.assertEqual(store.state_path(TASK_ID).read_bytes(), before)
                self.assertNotIn('private-corruption', store.ledger_path.read_text())

    def test_reconciliation_refuses_changed_task_state_or_noninterruption_block(self):
        for case in ('fingerprint', 'reason', 'attempt', 'completed_step', 'bool', 'string', 'float'):
            with self.subTest(case=case):
                self.run_dir = self.root/('job-'+case)
                self.interrupt_after_output()
                store = FileStateStore(self.run_dir/'state')
                state = store.load_state(TASK_ID)
                if case == 'fingerprint': state.spec_fingerprint = 'different'
                elif case == 'reason': state.blocked_reason = 'verification_error_requires_reconciliation'
                elif case == 'attempt': state.attempts['unrelated'] = 1
                elif case == 'completed_step': state.completed_steps = ['prepare']
                else: state.attempts['prepare'] = {'bool': True, 'string': '1', 'float': 1.5}[case]
                store.save_state(state)
                before = store.state_path(TASK_ID).read_bytes()
                with self.assertRaisesRegex(BlockedAction, 'historical_reconciliation_'):
                    self.run_job(reconcile_verified_output=True)
                self.assertEqual(store.state_path(TASK_ID).read_bytes(), before)

    def test_reconciliation_refuses_new_task_and_changed_inputs(self):
        with self.assertRaisesRegex(BlockedAction, 'existing_task_required'):
            self.run_job(reconcile_verified_output=True)
        self.assertFalse((self.run_dir/'preparation.json').exists())
        self.interrupt_after_output()
        self.reviews.write_text('[]')
        store = FileStateStore(self.run_dir/'state')
        before = store.state_path(TASK_ID).read_bytes()
        with self.assertRaisesRegex(BlockedAction, 'output_conflict'):
            self.run_job(reconcile_verified_output=True)
        self.assertEqual(store.state_path(TASK_ID).read_bytes(), before)

    def test_reconciliation_cannot_run_while_task_lock_is_held(self):
        self.interrupt_after_output()
        store = FileStateStore(self.run_dir/'state')
        with store.task_lock(TASK_ID):
            with self.assertRaisesRegex(RuntimeError, 'task_already_running'):
                self.run_job(reconcile_verified_output=True)

    def interrupt_after_reconciliation(self):
        self.interrupt_after_output()
        original = FileStateStore._reconcile_blocked_step_locked
        def crash(store, *args, **kwargs):
            original(store, *args, **kwargs)
            raise KeyboardInterrupt()
        with patch.object(FileStateStore, '_reconcile_blocked_step_locked', crash):
            with self.assertRaises(KeyboardInterrupt):
                self.run_job(reconcile_verified_output=True)

    def test_repeated_recovery_survives_interruption_after_reconciliation_commit(self):
        self.interrupt_after_reconciliation()
        output = self.run_dir/'preparation.json'
        before = (output.read_bytes(), output.stat().st_mtime_ns)
        store = FileStateStore(self.run_dir/'state')
        self.assertEqual(store.load_state(TASK_ID).status, 'pending')
        with patch.object(HistoricalPreparationAdapter, 'run', side_effect=AssertionError('replayed')):
            recovered = self.run_job(reconcile_verified_output=True)
        self.assertEqual(recovered['outcome']['status'], 'completed')
        self.assertEqual(recovered['outcome']['executed_steps'], ())
        self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)
        self.assertEqual(len(store.load_state(TASK_ID).reconciliations), 1)

    def test_reconciled_pending_output_is_checked_before_completion_state_changes(self):
        self.interrupt_after_reconciliation()
        store = FileStateStore(self.run_dir/'state')
        before = store.state_path(TASK_ID).read_bytes()
        (self.run_dir/'preparation.json').write_text('private-corruption')
        with self.assertRaisesRegex(BlockedAction, 'readback_mismatch'):
            self.run_job(reconcile_verified_output=True)
        self.assertEqual(store.state_path(TASK_ID).read_bytes(), before)

    def test_reconciled_running_resume_skips_action(self):
        self.interrupt_after_reconciliation()
        store = FileStateStore(self.run_dir/'state')
        state = store.load_state(TASK_ID)
        state.status = 'running'
        store.save_state(state)
        with patch.object(HistoricalPreparationAdapter, 'run', side_effect=AssertionError('replayed')):
            receipt = self.run_job(reconcile_verified_output=True)
        self.assertEqual(receipt['outcome']['status'], 'completed')
        self.assertEqual(receipt['outcome']['executed_steps'], ())

    def test_pending_recovery_requires_exact_saved_reconciliation(self):
        for case in ('missing', 'unrelated', 'resolution', 'reason', 'extra', 'attempt', 'zero'):
            with self.subTest(case=case):
                self.run_dir = self.root/('pending-'+case)
                self.interrupt_after_reconciliation()
                store = FileStateStore(self.run_dir/'state')
                state = store.load_state(TASK_ID)
                if case == 'missing': state.reconciliations = []
                elif case == 'unrelated': state.reconciliations[0]['note'] = 'other_recovery'
                elif case == 'resolution': state.reconciliations[0]['resolution'] = 'not_applied'
                elif case == 'reason': state.reconciliations[0]['previous_blocked_reason'] = 'other_failure'
                elif case == 'extra': state.reconciliations.append(dict(state.reconciliations[0]))
                elif case == 'attempt': state.attempts['prepare'] = True
                else: state.attempts['prepare'] = 0
                store.save_state(state)
                before = store.state_path(TASK_ID).read_bytes()
                with self.assertRaisesRegex(BlockedAction, 'interruption_required'):
                    self.run_job(reconcile_verified_output=True)
                self.assertEqual(store.state_path(TASK_ID).read_bytes(), before)

    def test_input_change_during_run_blocks_and_dry_run_cannot_write(self):
        adapter = HistoricalPreparationAdapter(records=self.records, reviews=self.reviews,
            output=self.root/'out.json', validation_start='2020-01-03T00:00:00Z', test_start='2020-01-04T00:00:00Z')
        with self.assertRaisesRegex(BlockedAction, 'write_not_authorized'): adapter.run({}, {'dry_run': True})
        self.records.write_text('{}')
        with self.assertRaisesRegex(BlockedAction, 'input_changed'): adapter.run({}, {})
        self.assertFalse((self.root/'out.json').exists())

    def test_private_sibling_workspace_allowed_but_project_output_rejected(self):
        # A workspace parent can have its own metadata; only the public project
        # boundary is fixed here. The caller remains responsible for private storage.
        (self.root/'.git').mkdir()
        self.assertEqual(self.run_job()['outcome']['status'], 'completed')
        self.run_dir = REPOSITORY/'must-not-create-private-fixture'
        with self.assertRaisesRegex(ValueError, 'outside_repository'): self.run_job()
        self.assertFalse(self.run_dir.exists())


if __name__ == '__main__':
    unittest.main()

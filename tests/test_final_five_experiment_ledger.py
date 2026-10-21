from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.final_five_challenger_preview import FrozenChallenger
from ml.final_five_experiment_ledger import ExperimentLedger, ExperimentStore, validate_payload
from ml.final_five_ranker import replay_experiment, run_experiment
from ml.model_history import _digest
from ml.synthetic_session import SessionSaveError
from test_final_five_ranker import fixtures
from test_synthetic_workbench_final_five_review import result


class ExperimentLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.cutoff = fixtures()
        cls.expected = run_experiment(cls.records, cls.cutoff, synthetic=True)

    def register(self, ledger, key='1', records=None, cutoff=None, retry_of=None):
        return ledger.register(self.records if records is None else records,
                               self.cutoff if cutoff is None else cutoff, key * 32,
                               '合成実験・固定条件を事前登録', retry_of=retry_of)

    def test_registration_precedes_fit_restore_replay_and_terminal_retry_never_refit(self):
        import lightgbm
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True); path = Path(root)/ExperimentStore.filename
            original = deepcopy(self.records)
            try:
                with patch('lightgbm.train', side_effect=AssertionError('registration must not fit')):
                    registered = self.register(ledger)
                    self.assertEqual(registered['attempt']['status'], 'registered')
                    saved = path.read_bytes(); self.assertEqual(self.register(ledger), registered)
                    self.assertEqual(path.read_bytes(), saved)
                actual_train = lightgbm.train
                def fit(*args, **kwargs):
                    on_disk = json.loads(path.read_text())['payload']['attempts'][0]
                    self.assertEqual(on_disk['status'], 'running')
                    self.assertIsNotNone(on_disk['started_at']); self.assertIsNone(on_disk['result'])
                    return actual_train(*args, **kwargs)
                with patch('lightgbm.train', side_effect=fit) as trained:
                    completed = ledger.run('1'*32); self.assertEqual(trained.call_count, 1)
                self.assertEqual(ledger.export('1'*32), self.expected)
                self.assertEqual(self.records, original)
                self.assertEqual(completed['attempt']['status'], 'completed')
                self.assertFalse(completed['evaluation_eligible']); self.assertFalse(completed['product_acceptance'])
                saved = path.read_bytes()
                with patch('lightgbm.train', side_effect=AssertionError('response retry must not fit')):
                    self.assertEqual(ledger.run('1'*32), completed)
                    self.assertEqual(self.register(ledger), completed)
                self.assertEqual(path.read_bytes(), saved)
            finally: ledger.close()
            with patch('lightgbm.train', side_effect=AssertionError('restore must not fit')):
                restored = ExperimentLedger(root, synthetic=True)
                try:
                    self.assertEqual(restored.show('1'*32), completed)
                    self.assertEqual(restored.export('1'*32), self.expected)
                    summary = restored.inspect()
                    self.assertNotIn('model_text', json.dumps(summary))
                    self.assertEqual(summary['attempt_count'], 1)
                finally: restored.close()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_blocked_attempts_keep_plan_and_never_train(self):
        cases = [[], self.records[:14],
                 [result(r['snapshot'], 3) if i < 14 else r for i, r in enumerate(self.records)]]
        with patch('lightgbm.train', side_effect=AssertionError('blocked must not fit')):
            for records in cases:
                with TemporaryDirectory() as root:
                    ledger = ExperimentLedger(root, synthetic=True)
                    try:
                        registered = self.register(ledger, records=records)
                        completed = ledger.run('1'*32)
                        self.assertEqual(completed['attempt']['status'], 'blocked')
                        self.assertEqual(completed['report']['status'], registered['attempt']['plan']['eligibility'])
                        self.assertEqual(completed['report']['training_runs'], 0)
                        with self.assertRaisesRegex(ValueError, 'completed_model_required'): ledger.export('1'*32)
                    finally: ledger.close()

    def test_failure_and_explicit_retry_preserve_prior_attempt(self):
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                self.register(ledger)
                with patch('lightgbm.train', side_effect=RuntimeError('private diagnostic')):
                    with self.assertRaisesRegex(RuntimeError, 'private diagnostic'): ledger.run('1'*32)
                failed = ledger.show('1'*32)
                self.assertEqual(failed['attempt']['status'], 'failed')
                self.assertNotIn('private diagnostic', json.dumps(ledger.payload))
                with patch('lightgbm.train', side_effect=AssertionError('no implicit retry')):
                    self.assertEqual(ledger.run('1'*32), failed)
                    with self.assertRaisesRegex(ValueError, 'retry_reference_required'): self.register(ledger, '2')
                    with self.assertRaisesRegex(ValueError, 'retry_reference_invalid'): self.register(ledger, '2', retry_of='9'*32)
                self.register(ledger, '2', retry_of='1'*32)
                self.assertEqual(ledger.run('2'*32)['attempt']['status'], 'completed')
                self.assertEqual(ledger.show('1'*32), failed)
                rows = ledger.inspect()['attempts']
                self.assertEqual(rows[1]['previous_registered_overlap'][0]['validation_reused'], 8)
                self.assertEqual(rows[1]['retry_of'], '1'*32)
            finally: ledger.close()

    def test_keyboard_interrupt_requires_explicit_abandonment(self):
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                self.register(ledger)
                with patch('lightgbm.train', side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt): ledger.run('1'*32)
            finally: ledger.close()
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                self.assertEqual(ledger.show('1'*32)['attempt']['status'], 'running')
                with patch('lightgbm.train', side_effect=AssertionError('no implicit retry')):
                    with self.assertRaisesRegex(ValueError, 'outcome_unknown'): ledger.run('1'*32)
                    with self.assertRaisesRegex(ValueError, 'unfinished_requires_resolution'): self.register(ledger, '2', retry_of='1'*32)
                    abandoned = ledger.abandon('1'*32, '中断確認・結果未保存')
                    self.assertEqual(ledger.abandon('1'*32, '中断確認・結果未保存'), abandoned)
                    self.assertEqual(ledger.run('1'*32), abandoned)
                self.register(ledger, '2', retry_of='1'*32)
                self.assertEqual(ledger.inspect()['attempt_count'], 2)
            finally: ledger.close()

    def test_overlap_survives_input_reordering_cutoff_changes_and_unrun_attempts(self):
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                with patch('lightgbm.train', side_effect=AssertionError('audit does not train')):
                    self.register(ledger); ledger.abandon('1'*32, '未実行のまま取り下げ')
                    self.register(ledger, '2', records=list(reversed(self.records)))
                    ledger.abandon('2'*32, '順序変更の監査')
                    # Later boundary moves two former validation races into training.
                    later = self.records[16]['prediction_timestamp']
                    self.register(ledger, '3', cutoff=later)
                    ledger.abandon('3'*32, '境界変更の監査')
                    # Earlier boundary exposes two former training races to validation.
                    self.register(ledger, '4', cutoff=self.records[12]['prediction_timestamp'])
                    rows = ledger.inspect()['attempts']
                self.assertEqual(rows[1]['previous_registered_overlap'][0]['validation_reused'], 8)
                overlap = rows[2]['previous_registered_overlap'][0]
                self.assertEqual((overlap['validation_reused'], overlap['training_previously_validation']), (6, 2))
                self.assertEqual(rows[3]['previous_registered_overlap'][0]['validation_previously_training'], 2)
                self.assertNotEqual(rows[0]['input_sha256'], rows[1]['input_sha256'])
                self.assertFalse(ledger.inspect()['independent_evaluation_established'])
            finally: ledger.close()

    def test_registration_preserves_holds_conflicts_and_input_exclusions(self):
        records = deepcopy(self.records)
        held = result(records[0]['snapshot'], status='withdrawn')
        conflict = result(records[2]['snapshot'], 0)
        records += [held, conflict, None, deepcopy(records[6])]
        original = deepcopy(records)
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                with patch('lightgbm.train', side_effect=AssertionError('registration cannot train')):
                    row = self.register(ledger, records=records)['attempt']
                plan = row['plan']; used = {r['race_id'] for r in plan['training'] + plan['validation']}
                self.assertNotIn(held['race_id'], used); self.assertNotIn(conflict['race_id'], used)
                self.assertEqual((plan['counts']['held_races'], plan['counts']['duplicate_snapshots_removed']), (1, 1))
                self.assertEqual(plan['counts']['training_races'], 12)
                self.assertIn('ml_history_schema_mismatch', plan['counts']['excluded'])
                self.assertEqual(ledger.payload['inputs'][row['input_sha256']], original)
                self.assertEqual(records, original)
            finally: ledger.close()

    def test_rehashed_plan_result_and_state_corruption_are_rejected_without_refit(self):
        with TemporaryDirectory() as root:
            ledger = ExperimentLedger(root, synthetic=True)
            self.register(ledger); ledger.run('1'*32); valid = deepcopy(ledger.payload); ledger.close()
            path = Path(root)/ExperimentStore.filename; original = path.read_bytes()
            def mutate(key, value):
                changed = deepcopy(valid); changed['attempts'][0][key] = value; return changed
            bad = [mutate('sequence', True), mutate('retry_of', '1'*32), mutate('started_at', None),
                   mutate('status', 'registered'), mutate('terminal_reason', 'made up')]
            changed = deepcopy(valid); changed['limits']['product_acceptance'] = True; bad.append(changed)
            changed = deepcopy(valid); changed['attempts'][0]['plan']['params']['num_leaves'] = 9; bad.append(changed)
            changed = deepcopy(valid); changed['attempts'][0]['result']['report']['strata'][0]['races'] += 1; bad.append(changed)
            changed = deepcopy(valid); changed['attempts'][0]['result']['report']['product_acceptance'] = True; bad.append(changed)
            changed = deepcopy(valid); model = changed['attempts'][0]['result']['model']
            model['training_manifest'][0]['history_sha256'] = '0'*64
            model['sha256'] = _digest({k:v for k,v in model.items() if k != 'sha256'}); bad.append(changed)
            with patch('lightgbm.train', side_effect=AssertionError('validation must not fit')):
                for value in bad:
                    path.write_text(json.dumps({'payload': value, 'sha256': _digest(value)}))
                    with self.assertRaises(ValueError): ExperimentLedger(root, synthetic=True)
                    self.assertEqual(json.loads(path.read_text())['payload'], value)
                path.write_bytes(original)
                restored = ExperimentLedger(root, synthetic=True); restored.close()
                self.assertEqual(replay_experiment(self.records, self.cutoff, self.expected['model'], synthetic=True), self.expected)

    def test_saving_registration_or_running_must_finish_before_training(self):
        for stage in ('register', 'run'):
            with TemporaryDirectory() as root:
                ledger = ExperimentLedger(root, synthetic=True)
                try:
                    if stage == 'run': self.register(ledger)
                    previous = deepcopy(ledger.payload)
                    with patch('lightgbm.train', side_effect=AssertionError('write must precede fit')) as fit:
                        with patch('ml.synthetic_session.os.fsync', side_effect=OSError('disk')):
                            with self.assertRaises(SessionSaveError):
                                self.register(ledger) if stage == 'register' else ledger.run('1'*32)
                        self.assertEqual(fit.call_count, 0)
                        self.assertEqual(ledger.payload, previous)
                        with self.assertRaises(SessionSaveError): ledger.inspect()
                finally: ledger.close()
                restored = ExperimentLedger(root, synthetic=True)
                try:
                    self.assertEqual(restored.inspect()['attempt_count'], 0 if stage == 'register' else 1)
                    if stage == 'run': self.assertEqual(restored.show('1'*32)['attempt']['status'], 'registered')
                finally: restored.close()

    def test_terminal_save_uncertainty_stops_process_and_preserves_one_attempt(self):
        for after_replace in (False, True):
            with TemporaryDirectory() as root:
                ledger = ExperimentLedger(root, synthetic=True); self.register(ledger)
                real_fsync = os.fsync; calls = 0
                def fail(fd):
                    nonlocal calls
                    calls += 1
                    # Two syncs commit running, then file/directory sync for completion.
                    if calls == (4 if after_replace else 3): raise OSError('terminal disk failure')
                    return real_fsync(fd)
                try:
                    with patch('ml.synthetic_session.os.fsync', side_effect=fail):
                        with self.assertRaises(SessionSaveError): ledger.run('1'*32)
                    self.assertEqual(ledger.payload['attempts'][0]['status'], 'running')
                    with self.assertRaises(SessionSaveError): ledger.run('1'*32)
                finally: ledger.close()
                with patch('lightgbm.train', side_effect=AssertionError('uncertain write must not refit')):
                    restored = ExperimentLedger(root, synthetic=True)
                    try:
                        self.assertEqual(restored.inspect()['attempt_count'], 1)
                        self.assertEqual(restored.show('1'*32)['attempt']['status'], 'completed' if after_replace else 'running')
                        if after_replace: restored.run('1'*32)
                        else:
                            with self.assertRaisesRegex(ValueError, 'outcome_unknown'): restored.run('1'*32)
                    finally: restored.close()

    def test_real_sigkill_during_training_and_before_after_terminal_replace(self):
        for boundary in ('training', 'before_replace', 'after_replace'):
            with TemporaryDirectory() as root:
                ledger = ExperimentLedger(root, synthetic=True); self.register(ledger); ledger.close()
                code = '''
import json, os, signal
from unittest.mock import patch
from ml.final_five_experiment_ledger import ExperimentLedger
ledger = ExperimentLedger(ROOT, synthetic=True)
original = os.replace
def kill_fit(*args, **kwargs): os.kill(os.getpid(), signal.SIGKILL)
def replace(src, dst, **kwargs):
    fd = os.open(src, os.O_RDONLY, dir_fd=kwargs['src_dir_fd'])
    with os.fdopen(fd) as f: status = json.load(f)['payload']['attempts'][0]['status']
    if status != 'completed': return original(src, dst, **kwargs)
    if BOUNDARY == 'after_replace': original(src, dst, **kwargs)
    os.kill(os.getpid(), signal.SIGKILL)
with patch('lightgbm.train', side_effect=kill_fit) if BOUNDARY == 'training' else patch('ml.synthetic_session.os.replace', side_effect=replace):
    ledger.run('1'*32)
'''.replace('ROOT', repr(root)).replace('BOUNDARY', repr(boundary))
                child = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
                self.assertEqual(child.returncode, -9, child.stderr)
                with patch('lightgbm.train', side_effect=AssertionError('restore cannot refit')):
                    restored = ExperimentLedger(root, synthetic=True)
                    try:
                        self.assertEqual(restored.inspect()['attempt_count'], 1)
                        status = restored.show('1'*32)['attempt']['status']
                        self.assertEqual(status, 'completed' if boundary == 'after_replace' else 'running')
                        if status == 'running':
                            with self.assertRaisesRegex(ValueError, 'outcome_unknown'): restored.run('1'*32)
                            restored.abandon('1'*32, '強制終了・結果不明を記録')
                            self.register(restored, '2', retry_of='1'*32)
                        else: restored.run('1'*32)
                    finally: restored.close()

    def test_gates_limits_conflicts_locks_and_external_changes(self):
        with TemporaryDirectory() as root:
            for flag in (False, 1, None):
                with self.assertRaises(ValueError): ExperimentLedger(Path(root)/'invalid', synthetic=flag)
            self.assertFalse((Path(root)/'invalid').exists())
            with self.assertRaisesRegex(ValueError, 'outside_repository'): ExperimentLedger(Path.cwd(), synthetic=True)
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                with self.assertRaisesRegex(ValueError, 'already_open'): ExperimentLedger(root, synthetic=True)
                for key, reason in (('x'*32, 'ok'), ('1'*32, ''), ('1'*32, 'bad\nreason')):
                    with self.assertRaises(ValueError): ledger.register(self.records, self.cutoff, key, reason)
                with patch('ml.final_five_experiment_ledger.MAX_RECORDS', 1):
                    with self.assertRaisesRegex(ValueError, 'input_limit'): self.register(ledger)
                self.register(ledger); ledger.abandon('1'*32, '未実行')
                path = Path(root)/ExperimentStore.filename; saved = path.read_bytes()
                with self.assertRaisesRegex(ValueError, 'id_conflict'):
                    ledger.register(self.records, self.cutoff, '1'*32, 'changed')
                for name in ('MAX_ATTEMPTS', 'MAX_INPUTS'):
                    with patch('ml.final_five_experiment_ledger.'+name, 1):
                        with self.assertRaisesRegex(ValueError, 'ledger_limit'):
                            self.register(ledger, '2', records=list(reversed(self.records)))
                    self.assertEqual(path.read_bytes(), saved)
                path.write_text('external change')
                with self.assertRaises(SessionSaveError): ledger.inspect()
                with self.assertRaises(SessionSaveError): ledger.run('1'*32)
                self.assertEqual(path.read_text(), 'external change')
            finally: ledger.close()
            with self.assertRaises(SessionSaveError): ledger.inspect()

    def test_cli_separate_process_registration_run_export_and_frozen_model_compatibility(self):
        with TemporaryDirectory() as root:
            root = Path(root); source = root/'histories.json'; state = root/'state'; output = root/'experiment.json'
            source.write_text(json.dumps(self.records)); original = source.read_bytes()
            prefix = [sys.executable, '-m', 'ml.final_five_experiment_ledger']
            common = ['--synthetic', '--state-dir', str(state)]
            register = ['register', str(source), '--cutoff', self.cutoff, '--attempt-id', '1'*32, '--reason', 'CLI合成実験']
            no_gate = subprocess.run(prefix+register+common[1:], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(no_gate.returncode, 0); self.assertFalse(state.exists())
            outputs = []
            for command in (register, ['run', '1'*32], ['show', '1'*32], ['run', '1'*32], ['inspect'],
                            ['export', '1'*32, '--output', str(output)]):
                response = subprocess.run(prefix+command+common, capture_output=True, text=True, timeout=30)
                self.assertEqual(response.returncode, 0, response.stderr); outputs.append(json.loads(response.stdout))
            self.assertEqual(outputs[1], outputs[2]); self.assertEqual(outputs[1], outputs[3])
            self.assertEqual(outputs[4]['attempt_count'], 1)
            self.assertEqual(json.loads(output.read_text()), self.expected)
            frozen = FrozenChallenger(output)
            self.assertEqual(frozen.view(self.records[14]['snapshot'], self.records[14]['snapshot']['snapshot_sha256'][:32])['status'], 'ready')
            saved = output.read_bytes()
            again = subprocess.run(prefix+['export', '1'*32, '--output', str(output)]+common,
                                   capture_output=True, text=True, timeout=30)
            self.assertNotEqual(again.returncode, 0); self.assertEqual(output.read_bytes(), saved)
            self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

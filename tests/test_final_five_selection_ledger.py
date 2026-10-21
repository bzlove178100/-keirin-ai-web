from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.final_five_challenger_preview import MAX_BYTES as INPUT_BYTES
from ml.final_five_selection_ledger import SelectionLedger, SelectionStore, validate_payload, _read_snapshot
from ml.final_five_ranker import run_experiment
from ml.model_history import _canonical, _digest
from ml.synthetic_session import SessionSaveError
from test_final_five_ranker import fixtures
from test_synthetic_workbench_final_five_review import dated_snapshot, result


class SelectionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.cutoff = fixtures()
        cls.experiment = run_experiment(cls.records, cls.cutoff, synthetic=True)
        changed = [result(r['snapshot'], 0) if i < 14 else r for i, r in enumerate(cls.records)]
        cls.other = run_experiment(changed, cls.cutoff, synthetic=True)['model']
        cls.model = cls.experiment['model']
        cls.snapshot = cls.records[14]['snapshot']

    def record(self, ledger, key='1', model=None, snapshot=None, reason='合成比較を保存'):
        return ledger.record(self.model if model is None else model,
                             self.snapshot if snapshot is None else snapshot, key * 32, reason)

    def test_seven_nine_budgets_restore_no_training_and_source_independence(self):
        with TemporaryDirectory() as root:
            ledger = SelectionLedger(root, synthetic=True)
            model, records = deepcopy(self.model), deepcopy(self.records)
            try:
                with patch('lightgbm.train', side_effect=AssertionError('receipt must never train')):
                    for i, (count, day) in enumerate((c, d) for c in (7, 9) for d in (7, 9, 10)):
                        response = self.record(ledger, str(i+1), snapshot=dated_snapshot(count, day, {7:5,9:3,10:4}[day]))
                        comparison = response['receipt']['comparison']
                        self.assertEqual(comparison['baseline']['selected_count'], comparison['challenger']['selected_count'])
                        self.assertEqual(response['evaluation_eligible'], False)
                        self.assertEqual(response['training_attempts_tracked'], False)
                    payload = deepcopy(ledger.payload); summary = ledger.inspect()
            finally: ledger.close()
            with patch('lightgbm.train', side_effect=AssertionError('restore must never train')):
                restored = SelectionLedger(root, synthetic=True)
                try:
                    self.assertEqual(restored.payload, payload); self.assertEqual(restored.inspect(), summary)
                    response = restored.receipt('1'*32); response['receipt']['reason'] = 'changed copy'
                    self.assertNotEqual(restored.receipt('1'*32), response)
                finally: restored.close()
            self.assertEqual(model, self.model); self.assertEqual(records, self.records)
            self.assertEqual((Path(root)/SelectionStore.filename).stat().st_mode & 0o777, 0o600)

    def test_idempotent_retry_conflict_and_reselection_are_not_collapsed(self):
        with TemporaryDirectory() as root:
            ledger = SelectionLedger(root, synthetic=True); path = Path(root)/SelectionStore.filename
            try:
                first = self.record(ledger); original = path.read_bytes()
                self.assertEqual(self.record(ledger), first); self.assertEqual(path.read_bytes(), original)
                for kwargs in ({'reason':'changed'}, {'model':self.other}, {'snapshot':self.records[15]['snapshot']}):
                    with self.assertRaisesRegex(ValueError, 'request_id_conflict'): self.record(ledger, **kwargs)
                    self.assertEqual(path.read_bytes(), original)
                self.record(ledger, '2'); self.record(ledger, '3', model=self.other)
                summary = ledger.inspect(); rows = summary['receipts']
                self.assertEqual(summary['receipt_count'], 3); self.assertEqual(summary['model_count'], 2)
                self.assertEqual([r['previous_same_race'] for r in rows], [0,1,2])
                self.assertEqual([r['previous_same_pair'] for r in rows], [0,1,0])
                self.assertEqual([r['different_model_seen'] for r in rows], [False,False,True])
                self.assertEqual(ledger.receipt('1'*32), first)
                encoded = json.dumps(summary)
                for name in ('model_text', 'training_manifest', 'trifecta_scores', 'hit_rate'):
                    self.assertNotIn(name, encoded)
            finally: ledger.close()

    def test_invalid_gate_reason_time_or_model_refused_without_receipt(self):
        with TemporaryDirectory() as root:
            directory = Path(root)/'state'
            for flag in (False, None, 1):
                with self.assertRaisesRegex(ValueError, 'synthetic'): SelectionLedger(directory, synthetic=flag)
            self.assertFalse(directory.exists())
            with self.assertRaisesRegex(ValueError, 'outside_repository'):
                SelectionLedger(Path(__file__).resolve().parents[1]/'ledger-test-must-not-exist', synthetic=True)
            ledger = SelectionLedger(directory, synthetic=True)
            try:
                for reason in ('', ' ', 'x'*501, 'bad\nreason'):
                    with self.assertRaisesRegex(ValueError, 'reason_invalid'): self.record(ledger, reason=reason)
                with self.assertRaisesRegex(ValueError, 'request_id_invalid'): self.record(ledger, 'z')
                with self.assertRaisesRegex(ValueError, 'training_race'): self.record(ledger, snapshot=self.records[0]['snapshot'])
                artifact = deepcopy(self.model); artifact['sha256'] = '0'*64
                with self.assertRaisesRegex(ValueError, 'digest_mismatch'): self.record(ledger, model=artifact)
                snapshot = deepcopy(self.snapshot); snapshot['prediction']['model_artifact']['evidence_scope'] = 'real'
                with self.assertRaises(ValueError): self.record(ledger, snapshot=snapshot)
                self.assertEqual(ledger.inspect()['receipt_count'], 0)
                self.assertFalse((directory/SelectionStore.filename).exists())
            finally: ledger.close()

    def test_recomputed_receipts_references_limits_and_sources_reject_rehashed_corruption(self):
        with TemporaryDirectory() as root:
            ledger = SelectionLedger(root, synthetic=True)
            try: self.record(ledger); good = deepcopy(ledger.payload)
            finally: ledger.close()
            mutations = [
                lambda p:p['receipts'][0]['comparison']['challenger']['picks'][0].update(ranking_score=999),
                lambda p:p['receipts'][0]['comparison']['baseline']['picks'][0].update(odds=999),
                lambda p:p['receipts'][0].update(sequence=True),
                lambda p:p['receipts'][0].update(model_sha256='0'*64),
                lambda p:p['limits'].update(evaluation_eligible=True),
                lambda p:p['receipts'].append(deepcopy(p['receipts'][0])),
                lambda p:p['models'][self.model['sha256']].update(model_text='broken'),
                lambda p:p['snapshots'][self.snapshot['snapshot_sha256']].update(captured_at='bad'),
                lambda p:p['snapshots'].update({'0'*64:self.snapshot}),
            ]
            path = Path(root)/SelectionStore.filename
            for mutate in mutations:
                bad = deepcopy(good); mutate(bad)
                data = _canonical({'payload':bad, 'sha256':_digest(bad)})
                path.write_text(data)
                with self.assertRaises((ValueError, KeyError, TypeError)): SelectionLedger(root, synthetic=True)
                self.assertEqual(path.read_text(), data)

    def test_bounds_do_not_evict_or_overwrite_previous_selection(self):
        with TemporaryDirectory() as root:
            ledger = SelectionLedger(root, synthetic=True)
            try:
                self.record(ledger); original = ledger.store.expected
                cases = [('MAX_RECEIPTS', 1, {}), ('MAX_MODELS', 1, {'model':self.other}),
                         ('MAX_SNAPSHOTS', 1, {'snapshot':self.records[15]['snapshot']}), ('MAX_BYTES', 1, {})]
                for name, limit, kwargs in cases:
                    with patch('ml.final_five_selection_ledger.'+name, limit):
                        with self.assertRaisesRegex(ValueError, 'limit|too_large'): self.record(ledger, '2', **kwargs)
                    self.assertEqual(ledger.store.expected, original)
                    self.assertEqual(ledger.inspect()['receipt_count'], 1)
                with patch('ml.final_five_selection_ledger.MAX_RECEIPTS', 1):
                    self.assertEqual(self.record(ledger)['receipt']['sequence'], 1)
            finally: ledger.close()

    def test_write_failure_and_uncertain_directory_sync_require_restart(self):
        for after_replace in (False, True):
            with self.subTest(after_replace=after_replace), TemporaryDirectory() as root:
                ledger = SelectionLedger(root, synthetic=True); self.record(ledger)
                original = deepcopy(ledger.payload); fsync = os.fsync; calls = []
                def failing_sync(fd):
                    calls.append(fd)
                    if len(calls) == (2 if after_replace else 1): raise OSError('synthetic disk failure')
                    fsync(fd)
                try:
                    with patch('ml.synthetic_session.os.fsync', side_effect=failing_sync):
                        with self.assertRaisesRegex(SessionSaveError, 'uncertain' if after_replace else 'save_failed'):
                            self.record(ledger, '2')
                    self.assertEqual(ledger.payload, original)
                    with self.assertRaisesRegex(SessionSaveError, 'restart_required'): ledger.inspect()
                    with self.assertRaisesRegex(SessionSaveError, 'restart_required'): self.record(ledger, '2')
                finally: ledger.close()
                restored = SelectionLedger(root, synthetic=True)
                try:
                    self.assertEqual(restored.inspect()['receipt_count'], 2 if after_replace else 1)
                    self.record(restored, '2')
                    self.assertEqual(restored.inspect()['receipt_count'], 2)
                finally: restored.close()

    def test_sigkill_before_and_after_replace_restore_complete_checkpoint(self):
        for after_replace in (False, True):
            with self.subTest(after_replace=after_replace), TemporaryDirectory() as root:
                ledger = SelectionLedger(root, synthetic=True); self.record(ledger); ledger.close()
                code = '''import os, signal
from unittest.mock import patch
from ml.final_five_selection_ledger import SelectionLedger
ledger = SelectionLedger(ROOT, synthetic=True)
row = ledger.payload['receipts'][0]
replace = os.replace
def kill(*args, **kwargs):
    if AFTER: replace(*args, **kwargs)
    os.kill(os.getpid(), signal.SIGKILL)
with patch('ml.synthetic_session.os.replace', side_effect=kill):
    ledger.record(ledger.payload['models'][row['model_sha256']], ledger.payload['snapshots'][row['snapshot_sha256']], '2'*32, row['reason'])
'''.replace('ROOT', repr(root)).replace('AFTER', repr(after_replace))
                child = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
                self.assertEqual(child.returncode, -9, child.stderr)
                restored = SelectionLedger(root, synthetic=True)
                try:
                    self.assertEqual(restored.inspect()['receipt_count'], 2 if after_replace else 1)
                    self.record(restored, '2'); self.assertEqual(restored.inspect()['receipt_count'], 2)
                finally: restored.close()

    def test_lock_external_changes_and_unsafe_input_files(self):
        with TemporaryDirectory() as root:
            ledger = SelectionLedger(root, synthetic=True); self.record(ledger)
            path = Path(root)/SelectionStore.filename
            try:
                with self.assertRaisesRegex(ValueError, 'already_open'): SelectionLedger(root, synthetic=True)
                path.write_text('external change')
                with self.assertRaisesRegex(SessionSaveError, 'restart_required'): ledger.inspect()
                with self.assertRaisesRegex(SessionSaveError, 'restart_required'): self.record(ledger)
                self.assertEqual(path.read_text(), 'external change')
            finally: ledger.close()
            snapshot = Path(root)/'snapshot.json'; snapshot.write_text(json.dumps(self.snapshot))
            original = snapshot.read_bytes(); self.assertEqual(_read_snapshot(snapshot), self.snapshot)
            link = Path(root)/'link'; link.symlink_to(snapshot)
            with self.assertRaises(OSError): _read_snapshot(link)
            hard = Path(root)/'hard'; os.link(snapshot, hard)
            with self.assertRaisesRegex(ValueError, 'file_invalid'): _read_snapshot(snapshot)
            hard.unlink(); fifo = Path(root)/'fifo'; os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, 'file_invalid'): _read_snapshot(fifo)
            self.assertEqual(snapshot.read_bytes(), original)
            with snapshot.open('wb') as handle: handle.truncate(INPUT_BYTES+1)
            with self.assertRaisesRegex(ValueError, 'file_invalid'): _read_snapshot(snapshot)

    def test_cli_record_inspect_show_and_input_files_unchanged(self):
        with TemporaryDirectory() as root:
            root = Path(root); experiment = root/'experiment.json'; snapshot = root/'snapshot.json'; state = root/'state'
            experiment.write_text(json.dumps({**self.experiment, 'report':{'untrusted':'never rendered'}}))
            snapshot.write_text(json.dumps(self.snapshot)); originals = experiment.read_bytes(), snapshot.read_bytes()
            prefix = [sys.executable, '-m', 'ml.final_five_selection_ledger']
            common = ['--state-dir', str(state), '--synthetic']
            record = ['record', str(experiment), str(snapshot), '--request-id', '1'*32, '--reason', 'CLI合成確認']
            failure = subprocess.run(prefix+record+common[:-1], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(failure.returncode, 0); self.assertFalse(state.exists())
            outputs = []
            for command in (record, ['inspect'], ['show','1'*32], record):
                response = subprocess.run(prefix+command+common, capture_output=True, text=True, timeout=30)
                self.assertEqual(response.returncode, 0, response.stderr); outputs.append(json.loads(response.stdout))
                self.assertNotIn('untrusted', response.stdout); self.assertNotIn('model_text', response.stdout)
            self.assertEqual(outputs[0], outputs[2]); self.assertEqual(outputs[0], outputs[3])
            self.assertEqual(outputs[1]['receipt_count'], 1)
            self.assertEqual(originals, (experiment.read_bytes(), snapshot.read_bytes()))


if __name__ == '__main__':
    unittest.main()

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.final_five_preview import final_five_view
from ml.final_five_ranker import FEATURES, candidate_matrix, predict_ranker, run_experiment
from ml.model_history import _digest, race_key, settle_snapshot
from test_synthetic_workbench_final_five_review import dated_snapshot, digest, result


def fixtures():
    records = [result(dated_snapshot(count, day), 8 if day < 6 else 3)
               for day in range(7) for count in (7, 9)]
    for day, size, outcome in ((7, 5, 8), (8, 5, 3), (9, 3, 0), (10, 4, 6)):
        records.extend(result(dated_snapshot(count, day, size), outcome) for count in (7, 9))
    cutoff = dated_snapshot(day=7)['captured_at']
    return records, cutoff


class FinalFiveRankerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.cutoff = fixtures()
        cls.experiment = run_experiment(cls.records, cls.cutoff, synthetic=True)

    def test_fit_reload_paired_budgets_and_no_source_mutation(self):
        records = deepcopy(self.records)
        experiment = run_experiment(records, self.cutoff, synthetic=True)
        self.assertEqual(records, self.records)
        model, report = experiment['model'], experiment['report']
        self.assertEqual(experiment, self.experiment)
        self.assertEqual((report['training_runs'], report['training_races'], report['test_races']), (1, 14, 8))
        self.assertEqual((report['training_candidates'], report['training_positive_candidates']), (210, 12))
        self.assertEqual(len(model['training_manifest']), 14)
        self.assertEqual(model['features'], FEATURES)
        test_records = {r['race_id']: r for r in records[14:]}
        for row in report['per_race']:
            record = test_records[row['race_id']]
            snap = record['snapshot']
            view = predict_ranker(json.loads(json.dumps(model)), snap, synthetic=True)
            self.assertEqual([p['combo_key'] for p in view['picks']], row['challenger_combos'])
            baseline = final_five_view(snap, snap['snapshot_sha256'][:32])
            self.assertEqual([p['combo_key'] for p in baseline['picks']], row['baseline_combos'])
            pool, _ = candidate_matrix(snap)
            self.assertTrue(set(row['challenger_combos']) <= {p['combo_key'] for p in pool})
            self.assertEqual(len(row['challenger_combos']), len(row['baseline_combos']))
            self.assertEqual(len(set(row['challenger_combos'])), row['selected_count'])
            for p in view['picks']:
                original = next(c for c in pool if c['combo_key'] == p['combo_key'])
                for key in ('estimated_probability', 'odds', 'source_rank', 'source_category'):
                    self.assertEqual(p[key], original[key])
        for group in report['strata']:
            n = group['races']; self.assertEqual(n, 2 if group['selected_count'] == 5 else 1)
            self.assertEqual(sum(group[k] for k in ('challenger_only', 'baseline_only', 'both', 'neither')), n)
            self.assertEqual(group['baseline_hit_rate'], group['baseline_hits']/n)
            self.assertEqual(group['challenger_hit_rate'], group['challenger_hits']/n)
        self.assertEqual(report['first_stage_training_independence'], 'not_independently_verified')
        for key in ('real_data_training_enabled', 'production_prediction_enabled', 'db_write_enabled', 'external_fetch_enabled', 'monetary_ev_enabled', 'promotion_eligible', 'product_acceptance'):
            self.assertIs(report[key], False)

    def test_holdout_labels_and_settlement_odds_do_not_change_model_or_predictions(self):
        changed = deepcopy(self.records)
        for i in range(14, len(changed)):
            changed[i] = result(changed[i]['snapshot'], 0, odds=999)
        after = run_experiment(changed, self.cutoff, synthetic=True)
        self.assertEqual(after['model'], self.experiment['model'])
        before_rows = self.experiment['report']['per_race']
        for before, row in zip(before_rows, after['report']['per_race']):
            self.assertEqual(before['challenger_combos'], row['challenger_combos'])
            self.assertEqual(before['baseline_combos'], row['baseline_combos'])
        # Training payout changes affect the input audit digest, never features,
        # labels, learned model text or candidate predictions.
        odds_changed = [settle_snapshot(r['snapshot'], {**r['settlement'], 'settlement_odds': 999}, synthetic=True)
                        for r in self.records]
        other = run_experiment(odds_changed, self.cutoff, synthetic=True)
        self.assertEqual(other['model']['model_text'], self.experiment['model']['model_text'])
        self.assertEqual(other['report']['per_race'], before_rows)

    def test_learning_uses_training_labels_and_keeps_outside_pool_negative_races(self):
        changed = [result(r['snapshot'], 0) if i < 14 else r for i, r in enumerate(self.records)]
        other = run_experiment(changed, self.cutoff, synthetic=True)
        self.assertNotEqual(other['model']['model_text'], self.experiment['model']['model_text'])
        self.assertNotEqual(other['report']['per_race'][0]['challenger_combos'], self.experiment['report']['per_race'][0]['challenger_combos'])
        self.assertEqual(self.experiment['report']['training_races'], 14)
        # This intentionally easy generated pattern proves wiring, not accuracy.
        self.assertGreater(self.experiment['report']['strata'][2]['challenger_only'], 0)

    def test_cutoff_boundary_purges_unavailable_results_and_normalizes_timezones(self):
        changed = deepcopy(self.records)
        changed[12] = settle_snapshot(changed[12]['snapshot'],
                        {**changed[12]['settlement'], 'result_timestamp': self.cutoff}, synthetic=True)
        boundary = datetime.fromisoformat(self.cutoff)
        changed[13] = settle_snapshot(changed[13]['snapshot'],
                        {**changed[13]['settlement'], 'result_timestamp': (boundary+timedelta(minutes=1)).isoformat()}, synthetic=True)
        run = run_experiment(changed, self.cutoff, synthetic=True)
        self.assertEqual((run['report']['training_races'], run['report']['test_races']), (12, 8))
        self.assertEqual(run['report']['excluded']['training_result_not_available_before_cutoff'], 2)
        self.assertTrue(all(datetime.fromisoformat(r['result_timestamp']) < boundary for r in run['model']['training_manifest']))
        utc_cutoff = boundary.astimezone(timezone.utc).isoformat()
        same = run_experiment(changed, utc_cutoff, synthetic=True)
        self.assertEqual(run['model']['model_text'], same['model']['model_text'])
        self.assertEqual(run['report']['per_race'], same['report']['per_race'])
        with self.assertRaisesRegex(ValueError, 'timezone_missing'):
            run_experiment(changed, '2026-10-24T10:00:00', synthetic=True)

    def test_holds_conflicts_invalid_duplicates_and_input_order(self):
        records = deepcopy(self.records)
        held = result(records[0]['snapshot'], status='withdrawn')
        conflict = result(records[2]['snapshot'], 0)
        corrupt = deepcopy(records[4]); corrupt['snapshot']['snapshot_sha256'] = '0'*64
        records += [held, conflict, corrupt, deepcopy(records[6]), None]
        run = run_experiment(records, self.cutoff, synthetic=True)
        report = run['report']; ids = {r['race_id'] for r in run['model']['training_manifest']}
        self.assertNotIn(held['race_id'], ids); self.assertNotIn(conflict['race_id'], ids)
        self.assertEqual((report['training_races'], report['held_races'], report['duplicate_snapshots_removed']), (12, 1, 1))
        for reason in ('nonstandard_race_requires_review', 'conflicting_settlements', 'snapshot_digest_mismatch', 'ml_history_schema_mismatch'):
            self.assertIn(reason, report['excluded'])
        self.assertEqual(run, run_experiment(list(reversed(records)), self.cutoff, synthetic=True))
        original = self.records[0]
        explicit = settle_snapshot(original['snapshot'], {**original['settlement'], 'result_status': 'normal'}, synthetic=True)
        normal_aliases = self.records+[explicit]
        aliases = run_experiment(normal_aliases, self.cutoff, synthetic=True)
        self.assertEqual(aliases, run_experiment(list(reversed(normal_aliases)), self.cutoff, synthetic=True))
        self.assertEqual(aliases['model'], self.experiment['model'])
        # Later snapshots of the same race cannot inflate training weight.
        old = self.records[6]; newer = deepcopy(old['snapshot'])
        newer['captured_at'] = (datetime.fromisoformat(newer['captured_at'])+timedelta(minutes=1)).isoformat(); digest(newer)
        recent = settle_snapshot(newer, old['settlement'], synthetic=True)
        result_run = run_experiment(self.records+[recent], self.cutoff, synthetic=True)
        manifest = next(r for r in result_run['model']['training_manifest'] if r['race_id'] == old['race_id'])
        self.assertEqual(manifest['snapshot_sha256'], newer['snapshot_sha256'])
        self.assertEqual(result_run['report']['training_races'], 14)

    def test_no_training_for_missing_times_labels_or_test_and_explicit_gate(self):
        with patch('lightgbm.train', side_effect=AssertionError('must not train')):
            for value in (False, None, 1):
                with self.assertRaises(ValueError): run_experiment(self.records, self.cutoff, synthetic=value)
            for value in (None, {}, '[]'):
                with self.assertRaises(ValueError): run_experiment(value, self.cutoff, synthetic=True)
            cases = [([], 'blocked_fewer_than_five_training_times'),
                     (self.records[:8]+self.records[14:], 'blocked_fewer_than_five_training_times'),
                     (self.records[:14], 'blocked_no_test_races'),
                     ([result(r['snapshot'], 3) if i < 14 else r for i, r in enumerate(self.records)], 'blocked_training_requires_both_labels')]
            for records, status in cases:
                blocked = run_experiment(records, self.cutoff, synthetic=True)
                self.assertIsNone(blocked['model']); self.assertEqual(blocked['report']['status'], status)
                self.assertEqual(blocked['report']['training_runs'], 0)
                self.assertEqual(blocked['report']['strata'], [])

    def test_empty_strata_are_null_and_prediction_rejects_seen_races_and_early_inputs(self):
        run = run_experiment(self.records[:16], self.cutoff, synthetic=True)
        for group in run['report']['strata']:
            if group['selected_count'] < 5:
                self.assertEqual(group['races'], 0)
                self.assertIsNone(group['baseline_hit_rate']); self.assertIsNone(group['challenger_hit_rate'])
        model = run['model']
        with self.assertRaisesRegex(ValueError, 'training_race_cannot_be_tested'):
            predict_ranker(model, self.records[0]['snapshot'], synthetic=True)
        unseen_old = dated_snapshot()
        unseen_old['prediction']['race']['venue'] = 'SYNTHETIC-UNSEEN'
        unseen_old['race_id'] = race_key(unseen_old['prediction']['race']); digest(unseen_old)
        with self.assertRaisesRegex(ValueError, 'prediction_precedes_cutoff'):
            predict_ranker(model, unseen_old, synthetic=True)
        for flag in (False, 1):
            with self.assertRaises(ValueError): predict_ranker(model, self.records[14]['snapshot'], synthetic=flag)

    def test_model_integrity_feature_allowlist_and_metadata_cannot_enable_real_modes(self):
        for mutate in (lambda m: m.update(sha256='0'*64),
                       lambda m: m['features'].append('settlement_odds'),
                       lambda m: m['limits'].update(production_prediction_enabled=True),
                       lambda m: m['training_manifest'][0].update(result_timestamp=self.cutoff),
                       lambda m: m['training_manifest'].append(deepcopy(m['training_manifest'][0]))):
            model = deepcopy(self.experiment['model']); mutate(model)
            if model['sha256'] != '0'*64:
                model['sha256'] = _digest({k: v for k, v in model.items() if k != 'sha256'})
            with self.assertRaises(ValueError): predict_ranker(model, self.records[14]['snapshot'], synthetic=True)
        damaged = deepcopy(self.records[14]['snapshot']); damaged['snapshot_sha256'] = '0'*64
        with self.assertRaises(ValueError): predict_ranker(self.experiment['model'], damaged, synthetic=True)

    def test_cli_fit_persist_reload_predict_and_refuse_overwrite(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); histories = root/'histories.json'; snapshot = root/'snapshot.json'
            artifact = root/'experiment.json'; output = root/'picks.json'
            histories.write_text(json.dumps(self.records)); snapshot.write_text(json.dumps(self.records[14]['snapshot']))
            originals = histories.read_bytes(), snapshot.read_bytes()
            command = [sys.executable, '-m', 'ml.final_five_ranker']
            def run(*args): return subprocess.run(command+list(args), capture_output=True, text=True)
            fit = run('fit', str(histories), '--cutoff', self.cutoff, '--synthetic', '--output', str(artifact))
            self.assertEqual(fit.returncode, 0, fit.stderr)
            saved = json.loads(artifact.read_text()); self.assertEqual(saved, self.experiment)
            prediction = run('predict', str(artifact), str(snapshot), '--synthetic', '--output', str(output))
            self.assertEqual(prediction.returncode, 0, prediction.stderr)
            expected = predict_ranker(saved['model'], self.records[14]['snapshot'], synthetic=True)
            self.assertEqual(json.loads(output.read_text()), expected)
            original_output = output.read_bytes()
            rejected = run('predict', str(artifact), str(snapshot), '--synthetic', '--output', str(output))
            self.assertEqual(rejected.returncode, 1); self.assertIn('output_already_exists', rejected.stderr)
            self.assertEqual(output.read_bytes(), original_output)
            self.assertNotEqual(run('fit', str(histories), '--cutoff', self.cutoff, '--output', str(root/'no-flag.json')).returncode, 0)
            self.assertFalse((root/'no-flag.json').exists())
            empty = root/'empty.json'; empty.write_text('[]')
            blocked = run('fit', str(empty), '--cutoff', self.cutoff, '--synthetic', '--output', str(root/'blocked.json'))
            self.assertEqual(blocked.returncode, 2); self.assertIsNone(json.loads((root/'blocked.json').read_text())['model'])
            self.assertEqual((histories.read_bytes(), snapshot.read_bytes()), originals)


if __name__ == '__main__': unittest.main()

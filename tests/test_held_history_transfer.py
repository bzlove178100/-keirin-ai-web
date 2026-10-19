from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.category_selection import select_model_categories
from ml.held_history import build_held_history, partition_holds, validate_held_history
from ml.held_history_transfer import export_target, transfer_hold, validate_transfer
from ml.model_history import _digest, evaluate_histories, race_key, settle_snapshot
from ml.settle_snapshot import build_history_record
from test_model_history import snapshot as model_snapshot, settlement as normal_model_event
from test_settle_snapshot import snapshot as baseline_snapshot


def snapshots(count=7):
    model = model_snapshot(count)
    # Deliberately different scores from the Phase32 fixture: a transfer must
    # preserve the target's prediction, not copy/relabel the source's table.
    scores = model['prediction']['trifecta_scores']
    scores[0]['estimated_probability'] *= 1.5
    scores[1]['estimated_probability'] *= 0.5
    model['prediction']['selected_predictions'] = select_model_categories(scores, count)
    rehash(model)
    phase = baseline_snapshot(source='GENERATED SYNTHETIC', rider_count=count)
    phase['race_data']['race'] = deepcopy(model['prediction']['race'])
    phase['captured_at'] = '2026-10-17T00:58:00Z'
    phase['snapshot_eligibility']['scheduled_start'] = '2026-10-17T02:00:00Z'
    return phase, model


def event(status='dead_heat', count=7, timestamp='2026-10-17T02:10:00Z'):
    value = {'result_status': status, 'result_timestamp': timestamp}
    if status == 'withdrawn':
        value['withdrawn_car_numbers'] = [count, 1]
    return value


def rehash(model):
    model['race_id'] = race_key(model['prediction']['race'])
    model['snapshot_sha256'] = _digest({k: v for k, v in model.items() if k != 'snapshot_sha256'})
    return model


class HeldHistoryTransferTests(unittest.TestCase):
    def test_both_directions_seven_nine_preserve_original_predictions(self):
        for count in (7, 9):
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                with self.subTest(count=count, status=status):
                    phase, model = snapshots(count)
                    held = build_held_history(phase, event(status, count))
                    originals = deepcopy((phase, model, held))
                    # Offline only: no socket connection, model execution or training.
                    with patch('socket.socket', side_effect=AssertionError('network forbidden')):
                        receipt = transfer_hold(held, model, synthetic=True)
                        validate_transfer(receipt, synthetic=True)
                        target = export_target(receipt, synthetic=True)
                        reverse = transfer_hold(target, phase, synthetic=True)
                    self.assertEqual((phase, model, held), originals)
                    self.assertEqual(receipt['source_history'], held)
                    self.assertEqual(target['snapshot'], model)
                    self.assertNotEqual(target['snapshot']['prediction']['trifecta_scores'][0]['estimated_probability'],
                                        phase['engine_response']['prediction']['trifecta_scores'][0]['estimated_probability'])
                    self.assertEqual(target['model_artifact_sha256'], model['prediction']['model_artifact']['sha256'])
                    self.assertEqual(target['settlement'], {**event(status, count), 'race_id': model['race_id']})
                    self.assertNotEqual(target['race_id'], held['race_id'])
                    self.assertEqual(reverse['target_history'], held)
                    validate_transfer(reverse, synthetic=True)
                    validate_held_history(reverse['target_history'])
                    for key in ('evaluation_eligible', 'supervised_training_eligible', 'hold_released',
                                'db_write_enabled', 'external_fetch_enabled', 'production_prediction_enabled',
                                'monetary_ev_enabled', 'promotion_eligible', 'provenance_independently_verified',
                                'supervised_training_enabled'):
                        self.assertIs(receipt[key], False)
                    for key in ('training_input', 'outcome_combo', 'settlement_odds'):
                        self.assertNotIn(key, target)
                        self.assertNotIn(key, target['settlement'])
                    self.assertEqual(receipt['car_numbers'], list(range(1, count + 1)))
                    self.assertEqual(receipt, transfer_hold(held, model, synthetic=True))
                    target['snapshot']['prediction']['model_artifact']['sha256'] = 'b' * 64
                    self.assertEqual(receipt['target_history']['snapshot'], model)
                    reverse['source_history']['snapshot']['prediction']['model_artifact']['sha256'] = 'c' * 64
                    self.assertEqual(model, originals[1])

    def test_transferred_holds_suppress_normal_histories_without_changing_other_race_metrics(self):
        for count in (7, 9):
            phase, model = snapshots(count)
            normal_ml = settle_snapshot(model, normal_model_event(model), synthetic=True)
            other_model = deepcopy(model)
            other_model['prediction']['race']['venue'] = 'OTHER SYNTHETIC'
            rehash(other_model)
            other_ml = settle_snapshot(other_model, normal_model_event(other_model), synthetic=True)
            reference = evaluate_histories([other_ml], synthetic=True)
            normal_phase = build_history_record(phase, outcome_combo='1-2-3', settlement_odds=40,
                                               result_timestamp='2026-10-17T02:10:00Z')
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                held_phase = build_held_history(phase, event(status, count))
                held_ml = export_target(transfer_hold(held_phase, model, synthetic=True), synthetic=True)
                for batch in ([normal_ml, held_ml], [held_ml, normal_ml], [held_ml, held_ml, normal_ml]):
                    report = evaluate_histories(batch, synthetic=True)
                    self.assertEqual(report['evaluated_races'], 0)
                    self.assertEqual(report['held_races'], 1)
                    self.assertEqual(report['metrics'], {})
                    mixed = evaluate_histories([*batch, other_ml], synthetic=True)
                    self.assertEqual(mixed['metrics'], reference['metrics'])
                    self.assertEqual(mixed['per_race'], reference['per_race'])
                returned = export_target(transfer_hold(held_ml, phase, synthetic=True), synthetic=True)
                for batch in ([normal_phase, returned], [returned, normal_phase], [returned, returned, normal_phase]):
                    kept, excluded, ids = partition_holds(batch)
                    self.assertEqual(kept, [])
                    self.assertEqual(ids, [normal_phase['race_id']])
                    self.assertEqual(excluded['race_has_held_result'], 1)

    def test_exact_identity_schedule_and_car_numbers_required(self):
        phase, model = snapshots()
        for field, value in (('venue', 'OTHER'), ('venue', 'synthetic'), ('race_number', 8)):
            bad = deepcopy(model)
            bad['prediction']['race'][field] = value
            rehash(bad)
            held = build_held_history(phase, event())
            with self.assertRaisesRegex(ValueError, 'race_identity_mismatch'):
                transfer_hold(held, bad, synthetic=True)
            held_model = settle_snapshot(bad, {**event(), 'race_id': bad['race_id']}, synthetic=True)
            with self.assertRaisesRegex(ValueError, 'race_identity_mismatch'):
                transfer_hold(held_model, phase, synthetic=True)
        bad = deepcopy(model)
        bad['scheduled_start'] = '2026-10-17T02:01:00Z'
        bad['prediction']['race']['scheduled_start_jst'] = bad['scheduled_start']
        rehash(bad)
        with self.assertRaisesRegex(ValueError, 'scheduled_start_mismatch'):
            transfer_hold(build_held_history(phase, event()), bad, synthetic=True)
        # Both snapshots individually valid, but different day must not match.
        other_phase = baseline_snapshot(source='GENERATED SYNTHETIC')
        other_phase['race_data']['race'].update(venue='SYNTHETIC', race_number=7)
        with self.assertRaisesRegex(ValueError, 'race_identity_mismatch'):
            transfer_hold(build_held_history(other_phase, event(timestamp='2026-10-17T02:10:00Z')), model, synthetic=True)
        phase9, model9 = snapshots(9)
        phase9['race_data']['race']['race_number'] = 7
        model9['prediction']['race']['race_number'] = 7
        rehash(model9)
        for source, target in ((build_held_history(phase9, event()), model),
                               (settle_snapshot(model9, {**event(), 'race_id': model9['race_id']}, synthetic=True), phase)):
            with self.assertRaisesRegex(ValueError, 'car_numbers_mismatch'):
                transfer_hold(source, target, synthetic=True)
        # No trimming/alias fallback; reject an invalid identity rather than guessing.
        phase['race_data']['race']['venue'] = 'SYNTHETIC '
        with self.assertRaisesRegex(ValueError, 'race_venue_required'):
            transfer_hold(build_held_history(phase, event()), model, synthetic=True)

    def test_timezones_and_event_after_both_captures(self):
        phase, model = snapshots()
        for status in ('withdrawn', 'cancelled'):
            early = event(status, timestamp='2026-10-17T10:30:00+09:00')
            receipt = transfer_hold(build_held_history(phase, early), model, synthetic=True)
            self.assertEqual(receipt['target_history']['settlement']['result_timestamp'], early['result_timestamp'])
            self.assertEqual(receipt['scheduled_start'], '2026-10-17T02:00:00+00:00')
            before_model = build_held_history(phase, event(status, timestamp='2026-10-17T00:59:00Z'))
            with self.assertRaisesRegex(ValueError, 'result_before_capture'):
                transfer_hold(before_model, model, synthetic=True)
            later_phase = deepcopy(phase)
            later_phase['captured_at'] = '2026-10-17T01:40:00Z'
            with self.assertRaisesRegex(ValueError, 'result_before_capture'):
                transfer_hold(receipt['target_history'], later_phase, synthetic=True)
        later_model = deepcopy(model)
        later_model['scheduled_start'] = '2026-10-17T03:00:00Z'
        later_model['prediction']['race']['scheduled_start_jst'] = later_model['scheduled_start']
        rehash(later_model)
        with self.assertRaisesRegex(ValueError, 'result_before_scheduled_start'):
            transfer_hold(build_held_history(phase, event()), later_model, synthetic=True)

    def test_synthetic_gate_schemas_and_validated_inputs(self):
        phase, model = snapshots()
        held = build_held_history(phase, event())
        receipt = transfer_hold(held, model, synthetic=True)
        for enabled in (False, None, 1, 'true'):
            with self.assertRaisesRegex(ValueError, 'explicit_synthetic'):
                transfer_hold(held, model, synthetic=enabled)
            with self.assertRaisesRegex(ValueError, 'explicit_synthetic'):
                validate_transfer(receipt, synthetic=enabled)
            with self.assertRaisesRegex(ValueError, 'explicit_synthetic'):
                export_target(receipt, synthetic=enabled)
        normal = settle_snapshot(model, normal_model_event(model), synthetic=True)
        for source in (None, {}, normal, {**held, 'schema_version': 'unknown'}):
            with self.assertRaises(ValueError):
                transfer_hold(source, model, synthetic=True)
        for target in (None, {}, phase, held):
            with self.assertRaises(ValueError):
                transfer_hold(held, target, synthetic=True)
        for source in ({**held, 'race_id': 'OTHER'}, {**held, 'db_write_enabled': 0},
                       {**held, 'outcome_combo': '1-2-3'},
                       {**held, 'settlement': {**event(), 'withdrawn_car_numbers': []}}):
            with self.assertRaises(ValueError):
                transfer_hold(source, model, synthetic=True)
        for mutate in (lambda m: m['prediction']['model_artifact'].update(sha256=None),
                       lambda m: m['prediction']['model_artifact'].update(evidence_scope='real'),
                       lambda m: m.update(db_write_enabled=True),
                       lambda m: m['prediction'].update(trifecta_scores=[])):
            bad = deepcopy(model)
            mutate(bad)
            rehash(bad)
            with self.assertRaises(ValueError):
                transfer_hold(held, bad, synthetic=True)

    def test_invalid_ml_source_and_phase32_target_cannot_be_relabelled(self):
        phase, model = snapshots()
        held = settle_snapshot(model, {**event(), 'race_id': model['race_id']}, synthetic=True)
        for mutate in (lambda h: h.update(model_artifact_sha256='b' * 64),
                       lambda h: h.update(db_write_enabled=0),
                       lambda h: h['snapshot'].update(snapshot_sha256='b' * 64),
                       lambda h: h['settlement'].update(race_id='other'),
                       lambda h: h.update(training_input={})):
            bad = deepcopy(held)
            mutate(bad)
            with self.assertRaises(ValueError):
                transfer_hold(bad, phase, synthetic=True)
        for mutate in (lambda s: s.update(validation_mode='replay'),
                       lambda s: s['engine_response'].update(engine_candidate='ml-model'),
                       lambda s: s['engine_response'].update(saved=True),
                       lambda s: s['race_data']['players'][0].update(car_number=2),
                       lambda s: s['engine_response']['prediction'].update(trifecta_scores=[])):
            bad = deepcopy(phase)
            mutate(bad)
            with self.assertRaises(ValueError):
                transfer_hold(held, bad, synthetic=True)

    def test_receipt_tampering_and_override_rejected_even_with_updated_digests(self):
        phase, model = snapshots()
        receipt = transfer_hold(build_held_history(phase, event()), model, synthetic=True)
        mutations = [lambda r: r.update(hold_released=True), lambda r: r.update(evaluation_eligible=0),
                     lambda r: r.update(override=True), lambda r: r.update(car_numbers=[1]),
                     lambda r: r.update(source_history_sha256='0' * 64),
                     lambda r: r['race_identity'].update(venue='OTHER'),
                     lambda r: r['source_history'].update(race_id='OTHER'),
                     lambda r: r['target_history'].update(model_artifact_sha256='b' * 64),
                     lambda r: r['target_history']['settlement'].update(result_status='cancelled'),
                     lambda r: r['target_history'].update(outcome_combo='1-2-3')]
        for mutate in mutations:
            bad = deepcopy(receipt)
            mutate(bad)
            bad['target_history_sha256'] = _digest(bad['target_history'])
            for operation in (validate_transfer, export_target):
                with self.assertRaises(ValueError):
                    operation(bad, synthetic=True)
        for malformed in (None, {}, {**receipt, 'target_history': None}):
            with self.assertRaises(ValueError):
                validate_transfer(malformed, synthetic=True)

    def test_cli_round_trip_no_overwrite_no_output_on_rejection(self):
        phase, model = snapshots()
        held = build_held_history(phase, event('withdrawn'))
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target, receipt, output = [root / name for name in ('source.json', 'target.json', 'receipt.json', 'held.json')]
            source.write_text(json.dumps(held), encoding='utf-8')
            target.write_text(json.dumps(model), encoding='utf-8')
            prefix = [sys.executable, '-m', 'ml.held_history_transfer']
            args = [*prefix, 'transfer', str(source), str(target), '--output', str(receipt)]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(receipt.exists())
            subprocess.run([*args, '--synthetic'], check=True, capture_output=True)
            receipt_bytes = receipt.read_bytes()
            rerun = subprocess.run([*args, '--synthetic'], capture_output=True)
            self.assertNotEqual(rerun.returncode, 0)
            self.assertEqual(receipt.read_bytes(), receipt_bytes)
            for existing in (source, target):
                before_input = existing.read_bytes()
                rejected = subprocess.run([*prefix, 'transfer', str(source), str(target),
                                           '--output', str(existing), '--synthetic'], capture_output=True)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(existing.read_bytes(), before_input)
            export = [*prefix, 'export-target', str(receipt), '--output', str(output), '--synthetic']
            subprocess.run(export, check=True, capture_output=True)
            exported = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(exported['snapshot'], model)
            self.assertEqual(evaluate_histories([exported], synthetic=True)['held_races'], 1)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(export, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            bad = json.loads(receipt_bytes)
            bad['hold_released'] = True
            invalid = root / 'invalid.json'
            invalid.write_text(json.dumps(bad), encoding='utf-8')
            absent = root / 'absent.json'
            rejected = subprocess.run([*prefix, 'export-target', str(invalid), '--output', str(absent), '--synthetic'], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(absent.exists())
            self.assertEqual(json.loads(source.read_text(encoding='utf-8')), held)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), model)


if __name__ == '__main__':
    unittest.main()

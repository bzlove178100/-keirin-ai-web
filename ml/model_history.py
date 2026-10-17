"""Capture, settle and review frozen ML output using generated synthetic data only.

No network, retraining, DB writes or promotion. This distinct schema is not a
Phase32 baseline or proof of independently verified pre-race provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from ml.category_selection import _number
from ml.offline_preview import validate_preview
from ml.probability_metrics import score
from ml.settle_snapshot import _iso

SNAPSHOT_SCHEMA = 'ml-prediction-snapshot-v1'
HISTORY_SCHEMA = 'ml-settled-history-v1'
HELD_SCHEMA = 'ml-held-history-v1'
HELD_STATUSES = ('dead_heat', 'withdrawn', 'cancelled')
SAFETY = {
    'evidence_scope': 'synthetic_test_only',
    'production_prediction_enabled': False, 'db_write_enabled': False,
    'external_fetch_enabled': False, 'monetary_ev_enabled': False,
    'promotion_eligible': False, 'supervised_training_enabled': False,
    'provenance_independently_verified': False,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _synthetic(enabled: bool) -> None:
    if enabled is not True:
        raise ValueError('explicit_synthetic_mode_required')


def _safety(value: dict) -> None:
    if _canonical({key: value.get(key) for key in SAFETY}) != _canonical(SAFETY):
        raise ValueError('synthetic_safety_flags_mismatch')


def race_key(race: Any) -> str:
    if not isinstance(race, dict):
        raise ValueError('race_identity_required')
    day, venue, number = (race.get(key) for key in ('date', 'venue', 'race_number'))
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('race_date_invalid')
    if not isinstance(venue, str) or not venue.strip() or venue != venue.strip():
        raise ValueError('race_venue_required')
    if type(number) is not int or number < 1:
        raise ValueError('race_number_invalid')
    # Structured identity avoids collisions caused by separator characters in venues.
    return 'ml-race-' + _digest([day, venue, number])


def validate_snapshot(snapshot: dict, *, synthetic: bool = False) -> None:
    _synthetic(synthetic)
    if not isinstance(snapshot, dict) or snapshot.get('schema_version') != SNAPSHOT_SCHEMA:
        raise ValueError('ml_snapshot_schema_mismatch')
    _safety(snapshot)
    if snapshot.get('clock_source') != 'local_unverified':
        raise ValueError('unverified_local_clock_required')
    payload = {key: value for key, value in snapshot.items() if key != 'snapshot_sha256'}
    if snapshot.get('snapshot_sha256') != _digest(payload):
        raise ValueError('snapshot_digest_mismatch')
    prediction = snapshot.get('prediction')
    validate_preview(prediction)
    if 'selected_predictions' not in prediction:
        raise ValueError('saved_category_selection_required')
    artifact = prediction.get('model_artifact') or {}
    if artifact.get('evidence_scope') != 'synthetic_test_only':
        raise ValueError('synthetic_model_artifact_required')
    if not isinstance(artifact.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', artifact['sha256']):
        raise ValueError('model_artifact_digest_required')
    trained = _iso(artifact.get('trained_at'), 'model_trained_at')
    generated = _iso(prediction.get('generated_at'), 'generated_at')
    captured = _iso(snapshot.get('captured_at'), 'captured_at')
    scheduled = _iso(snapshot.get('scheduled_start'), 'scheduled_start')
    if not trained <= generated <= captured < scheduled:
        raise ValueError('model_snapshot_time_order_invalid')
    race = prediction.get('race')
    if snapshot.get('race_id') != race_key(race):
        raise ValueError('race_identity_mismatch')
    if _iso(race.get('scheduled_start_jst'), 'race_scheduled_start') != scheduled:
        raise ValueError('scheduled_start_mismatch')
    if scheduled.astimezone(timezone(timedelta(hours=9))).date().isoformat() != race['date']:
        raise ValueError('race_date_schedule_mismatch')


def capture_prediction(prediction: dict, *, synthetic: bool = False) -> dict:
    _synthetic(synthetic)
    snapshot = {
        'schema_version': SNAPSHOT_SCHEMA, **SAFETY,
        'race_id': race_key(prediction.get('race')),
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'scheduled_start': prediction['race'].get('scheduled_start_jst'),
        'clock_source': 'local_unverified',
        'prediction': deepcopy(prediction),
    }
    snapshot['snapshot_sha256'] = _digest(snapshot)
    validate_snapshot(snapshot, synthetic=True)
    return snapshot


def settle_snapshot(snapshot: dict, settlement: dict, *, synthetic: bool = False) -> dict:
    validate_snapshot(snapshot, synthetic=synthetic)
    if not isinstance(settlement, dict) or settlement.get('race_id') != snapshot['race_id']:
        raise ValueError('settlement_race_mismatch')
    status = settlement.get('result_status', 'normal')
    if status not in ('normal', *HELD_STATUSES):
        raise ValueError('result_status_invalid')
    fields = {'race_id', 'result_timestamp'}
    if status == 'normal':
        fields |= {'outcome_combo', 'settlement_odds'}
        if 'result_status' in settlement:
            fields.add('result_status')
    else:
        fields.add('result_status')
        if status == 'withdrawn':
            fields.add('withdrawn_car_numbers')
    # Do not silently drop dead_heat, multiple outcomes or other undeclared data.
    if set(settlement) != fields:
        raise ValueError('settlement_fields_invalid')
    result_time = _iso(settlement.get('result_timestamp'), 'result_timestamp')
    if result_time < _iso(snapshot['captured_at'], 'captured_at'):
        raise ValueError('result_before_capture')
    if status in ('normal', 'dead_heat') and result_time < _iso(snapshot['scheduled_start'], 'scheduled_start'):
        raise ValueError('result_before_scheduled_start')
    if status == 'normal':
        outcome, odds = settlement['outcome_combo'], settlement['settlement_odds']
        valid_keys = {row['combo_key'] for row in snapshot['prediction']['trifecta_scores']}
        if not isinstance(outcome, str) or outcome not in valid_keys:
            raise ValueError('outcome_not_in_riders')
        if not _number(odds):
            raise ValueError('settlement_odds_invalid')
    if status == 'withdrawn':
        cars = settlement['withdrawn_car_numbers']
        count = snapshot['prediction']['input_quality']['rider_count']
        if (not isinstance(cars, list) or not cars or
                any(type(c) is not int or not 1 <= c <= count for c in cars) or
                len(set(cars)) != len(cars)):
            raise ValueError('withdrawn_cars_invalid')
    return {
        'schema_version': HISTORY_SCHEMA if status == 'normal' else HELD_SCHEMA, **SAFETY,
        'race_id': snapshot['race_id'], 'prediction_timestamp': snapshot['captured_at'],
        'model_artifact_sha256': snapshot['prediction']['model_artifact']['sha256'],
        'snapshot': deepcopy(snapshot),
        'settlement': deepcopy(settlement),
    }


def _validate_history(record: Any) -> None:
    if not isinstance(record, dict) or record.get('schema_version') not in (HISTORY_SCHEMA, HELD_SCHEMA):
        raise ValueError('ml_history_schema_mismatch')
    expected = settle_snapshot(record.get('snapshot'), record.get('settlement'), synthetic=True)
    if _canonical(record) != _canonical(expected):
        raise ValueError('history_does_not_match_snapshot')


def evaluate_histories(records: list[dict], *, synthetic: bool = False) -> dict:
    _synthetic(synthetic)
    groups: dict[str, list[dict]] = {}
    excluded: Counter = Counter()
    for record in records:
        try:
            _validate_history(record)
            groups.setdefault(record['race_id'], []).append(record)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            excluded[str(exc) if isinstance(exc, ValueError) else 'malformed_record'] += 1
    selected, held, duplicates = [], [], 0
    for group in groups.values():
        holds = [r for r in group if r['schema_version'] == HELD_SCHEMA]
        if holds:
            # A later ordinary record cannot erase an unresolved exception.
            held.append({'race_id': group[0]['race_id'],
                         'rider_count': group[0]['snapshot']['prediction']['input_quality']['rider_count'],
                         'reasons': sorted({r['settlement']['result_status'] for r in holds}),
                         'withdrawn_car_numbers': sorted({c for r in holds for c in r['settlement'].get('withdrawn_car_numbers', [])}),
                         'excluded_records': len(group)})
            excluded['nonstandard_race_requires_review'] += len(group)
            continue
        # Explicit normal and legacy omitted normal status mean the same event.
        if len({_canonical({**r['settlement'], 'result_status': 'normal'}) for r in group}) != 1:
            excluded['conflicting_settlements'] += len(group)
            continue
        latest = max(_iso(r['prediction_timestamp'], 'prediction_timestamp') for r in group)
        tied = [r for r in group if _iso(r['prediction_timestamp'], 'prediction_timestamp') == latest]
        if len({_canonical({**r, 'settlement': {**r['settlement'], 'result_status': 'normal'}}) for r in tied}) != 1:
            excluded['conflicting_latest_snapshots'] += len(group)
            continue
        selected.append(tied[0]); duplicates += len(group) - 1
    selected.sort(key=lambda r: (_iso(r['prediction_timestamp'], 'prediction_timestamp'), r['race_id']))
    per_race = []
    for record in selected:
        prediction, outcome = record['snapshot']['prediction'], record['settlement']['outcome_combo']
        per_race.append({
            'race_id': record['race_id'], 'model_artifact_sha256': record['model_artifact_sha256'],
            'rider_count': prediction['input_quality']['rider_count'],
            'prediction_timestamp': record['prediction_timestamp'],
            'metrics': score({r['combo_key']: r['estimated_probability'] for r in prediction['trifecta_scores']}, outcome),
            'categories': {key: {'selected_count': len(c['picks']),
                                'hit': any(p['combo_key'] == outcome for p in c['picks'])}
                           for key, c in prediction['selected_predictions']['categories'].items()},
        })
    fields = ('reciprocal_rank', 'log_loss', 'brier_sum', 'top1', 'top3', 'top5', 'top10')
    return {
        'evaluation_version': 'frozen-ml-history-review-v1', **SAFETY,
        'status': 'completed_synthetic_frozen_review' if per_race else 'blocked_no_valid_histories',
        'probability_calibration_status': 'uncalibrated',
        'input_records': len(records), 'evaluated_races': len(per_race),
        'held_races': len(held), 'held_cases': sorted(held, key=lambda r: r['race_id']),
        'model_artifacts': sorted({r['model_artifact_sha256'] for r in per_race}),
        'metrics_scope': 'pooled_frozen_synthetic_predictions',
        'excluded': dict(excluded), 'duplicate_snapshots_removed': duplicates,
        'metrics': {key: sum(r['metrics'][key] for r in per_race) / len(per_race) for key in fields} if per_race else {},
        'per_race': per_race,
        'note': 'Generated synthetic data only. Frozen predictions; no retraining, Phase32 comparison, holdout claim, monetary return or promotion. Digests detect accidental changes, not provenance or permission.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('capture', 'settle', 'evaluate'):
        command = commands.add_parser(name)
        command.add_argument('inputs', nargs='+' if name == 'evaluate' else (2 if name == 'settle' else 1), type=Path)
        command.add_argument('--synthetic', action='store_true', help='Required: generated synthetic data only.')
        command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    _synthetic(args.synthetic)
    inputs = [json.loads(path.read_text(encoding='utf-8')) for path in args.inputs]
    if args.command == 'capture':
        result = capture_prediction(inputs[0], synthetic=True)
    elif args.command == 'settle':
        result = settle_snapshot(*inputs, synthetic=True)
    else:
        result = evaluate_histories([record for item in inputs for record in (item if isinstance(item, list) else [item])], synthetic=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an existing prediction snapshot or its review evidence.
    with args.output.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'status': result.get('status', result['schema_version'] if 'schema_version' in result else '')}))
    return 2 if result.get('status') == 'blocked_no_valid_histories' else 0


if __name__ == '__main__':
    raise SystemExit(main())

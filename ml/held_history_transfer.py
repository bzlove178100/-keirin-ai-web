"""Transfer a held event between independently saved Phase32/ML snapshots.

Generated synthetic inputs only. Never convert predictions, invent an ML model,
release a hold, fetch data, train, or write to a database.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from ml import held_history, model_history
from ml.settle_snapshot import _iso

TRANSFER_SCHEMA = 'held-history-transfer-v1'
SAFETY = {
    **model_history.SAFETY,
    'evaluation_eligible': False,
    'supervised_training_eligible': False,
    'hold_released': False,
}


def _identity(snapshot: dict, *, phase32: bool) -> tuple[dict, datetime, list[int]]:
    if phase32:
        race = snapshot['race_data']['race']
        scheduled = _iso(snapshot['snapshot_eligibility']['scheduled_start'], 'scheduled_start')
        cars = sorted(player['car_number'] for player in snapshot['race_data']['players'])
    else:
        race = snapshot['prediction']['race']
        scheduled = _iso(snapshot['scheduled_start'], 'scheduled_start')
        cars = list(range(1, snapshot['prediction']['input_quality']['rider_count'] + 1))
    # Use structured identity, not schema-specific race_id parsing or aliases.
    model_history.race_key(race)
    if race['race_number'] > 12:
        raise ValueError('transfer_race_number_invalid')
    if scheduled.astimezone(timezone(timedelta(hours=9))).date().isoformat() != race['date']:
        raise ValueError('transfer_race_date_mismatch')
    return {key: race[key] for key in ('date', 'venue', 'race_number')}, scheduled, cars


def transfer_hold(source_history: dict, target_snapshot: dict, *, synthetic: bool = False) -> dict:
    """Keep both original snapshots; apply only the same held event to the target."""
    model_history._synthetic(synthetic)
    if not isinstance(source_history, dict) or not isinstance(target_snapshot, dict):
        raise ValueError('transfer_inputs_required')
    source_schema = source_history.get('schema_version')
    if source_schema == held_history.HELD_SCHEMA:
        held_history.validate_held_history(source_history)
        expected_target = model_history.SNAPSHOT_SCHEMA
        source_phase32 = True
    elif source_schema == model_history.HELD_SCHEMA:
        model_history._validate_history(source_history)
        expected_target = 'prediction-snapshot-v1'
        source_phase32 = False
    else:
        raise ValueError('transfer_source_must_be_held_history')
    if target_snapshot.get('schema_version') != expected_target:
        raise ValueError('transfer_requires_other_engine_snapshot')

    event = deepcopy(source_history['settlement'])
    if source_phase32:
        event['race_id'] = target_snapshot.get('race_id')
        target = model_history.settle_snapshot(target_snapshot, event, synthetic=True)
    else:
        del event['race_id']
        target = held_history.build_held_history(target_snapshot, event)

    source_identity, source_start, source_cars = _identity(source_history['snapshot'], phase32=source_phase32)
    target_identity, target_start, target_cars = _identity(target_snapshot, phase32=not source_phase32)
    if model_history._canonical(source_identity) != model_history._canonical(target_identity):
        raise ValueError('transfer_race_identity_mismatch')
    if source_start != target_start:
        raise ValueError('transfer_scheduled_start_mismatch')
    if source_cars != target_cars:
        raise ValueError('transfer_car_numbers_mismatch')

    return {
        'schema_version': TRANSFER_SCHEMA, **SAFETY,
        'race_identity': source_identity,
        'scheduled_start': source_start.astimezone(timezone.utc).isoformat(),
        'car_numbers': source_cars,
        'source_history_sha256': model_history._digest(source_history),
        'target_history_sha256': model_history._digest(target),
        'source_history': deepcopy(source_history),
        'target_history': target,
    }


def validate_transfer(receipt: dict, *, synthetic: bool = False) -> None:
    """Rebuild the complete receipt; digests are not provenance/permission proof."""
    model_history._synthetic(synthetic)
    if not isinstance(receipt, dict) or receipt.get('schema_version') != TRANSFER_SCHEMA:
        raise ValueError('transfer_schema_mismatch')
    target = receipt.get('target_history')
    if not isinstance(target, dict):
        raise ValueError('transfer_target_history_required')
    expected = transfer_hold(receipt.get('source_history'), target.get('snapshot'), synthetic=True)
    if model_history._canonical(receipt) != model_history._canonical(expected):
        raise ValueError('transfer_receipt_mismatch')


def export_target(receipt: dict, *, synthetic: bool = False) -> dict:
    """Export only after checking the receipt; retain the receipt for audit."""
    validate_transfer(receipt, synthetic=synthetic)
    return deepcopy(receipt['target_history'])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('transfer', 'export-target'):
        command = commands.add_parser(name)
        command.add_argument('inputs', nargs=2 if name == 'transfer' else 1, type=Path)
        command.add_argument('--synthetic', action='store_true', help='Required: generated synthetic inputs only.')
        command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    model_history._synthetic(args.synthetic)
    inputs = [json.loads(path.read_text(encoding='utf-8')) for path in args.inputs]
    result = (transfer_hold(*inputs, synthetic=True) if args.command == 'transfer'
              else export_target(inputs[0], synthetic=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # No overwrite of source, target snapshot, previous receipt or history.
    with args.output.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'schema_version': result['schema_version']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Audited held-event decisions and frozen scoring for generated synthetic inputs.

Original histories remain unchanged. Release applies only to this review report;
no training dataset, ordinary history export, network, database or promotion.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ml import held_history, model_history
from ml.category_selection import _number
from ml.held_history_transfer import _identity
from ml.probability_metrics import score
from ml.settle_snapshot import _iso

REVIEW_SCHEMA = 'held-history-review-v1'
EVIDENCE_SCHEMA = 'synthetic-result-evidence-v1'
REPORT_SCHEMA = 'held-history-review-report-v1'
SAFETY = {**model_history.SAFETY, 'supervised_training_eligible': False}


def _hold(record: dict) -> tuple[dict, datetime, list[int], str]:
    if not isinstance(record, dict):
        raise ValueError('review_held_history_required')
    schema = record.get('schema_version')
    if schema == held_history.HELD_SCHEMA:
        held_history.validate_held_history(record)
        engine = 'phase32'
    elif schema == model_history.HELD_SCHEMA:
        model_history._validate_history(record)
        engine = 'ml'
    else:
        raise ValueError('review_held_history_required')
    return (*_identity(record['snapshot'], phase32=engine == 'phase32'), engine)


def _table(record: dict, engine: str) -> dict:
    snapshot = record['snapshot']
    prediction = snapshot['engine_response']['prediction'] if engine == 'phase32' else snapshot['prediction']
    return {row['combo_key']: row['estimated_probability'] for row in prediction['trifecta_scores']}


def create_review(source_history: dict, evidence: dict, decision: dict, *, synthetic: bool = False) -> dict:
    model_history._synthetic(synthetic)
    identity, scheduled, cars, engine = _hold(source_history)
    evidence_fields = {'schema_version', 'evidence_scope', 'fixture_id', 'race_identity',
                       'scheduled_start', 'car_numbers', 'result'}
    if not isinstance(evidence, dict) or set(evidence) != evidence_fields:
        raise ValueError('review_evidence_fields_invalid')
    if evidence['schema_version'] != EVIDENCE_SCHEMA or evidence['evidence_scope'] != 'synthetic_test_only':
        raise ValueError('review_synthetic_evidence_required')
    if not isinstance(evidence['fixture_id'], str) or not re.fullmatch(r'generated-[A-Za-z0-9_-]{1,80}', evidence['fixture_id']):
        raise ValueError('review_fixture_id_invalid')
    if model_history._canonical(evidence['race_identity']) != model_history._canonical(identity):
        raise ValueError('review_evidence_identity_mismatch')
    if _iso(evidence['scheduled_start'], 'scheduled_start') != scheduled:
        raise ValueError('review_evidence_schedule_mismatch')
    if model_history._canonical(evidence['car_numbers']) != model_history._canonical(cars):
        raise ValueError('review_evidence_cars_mismatch')
    if not isinstance(decision, dict) or set(decision) != {'decision', 'reviewed_at', 'reviewer_id', 'reason'}:
        raise ValueError('review_decision_fields_invalid')
    action = decision['decision']
    if action not in ('correct_declaration', 'confirm_nonstandard'):
        raise ValueError('review_decision_invalid')
    if not isinstance(decision['reviewer_id'], str) or not re.fullmatch(r'synthetic-[A-Za-z0-9_-]{1,80}', decision['reviewer_id']):
        raise ValueError('review_synthetic_reviewer_required')
    reason = decision['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValueError('review_reason_required')
    result = evidence['result']
    if not isinstance(result, dict):
        raise ValueError('review_result_required')
    original = source_history['settlement']
    if action == 'correct_declaration':
        if set(result) != {'result_status', 'result_timestamp', 'outcome_combo', 'settlement_odds'}:
            raise ValueError('review_normal_result_fields_invalid')
        if result['result_status'] != 'normal':
            raise ValueError('review_normal_confirmation_required')
        if not isinstance(result['outcome_combo'], str) or result['outcome_combo'] not in _table(source_history, engine):
            raise ValueError('review_outcome_not_in_riders')
        if not _number(result['settlement_odds']):
            raise ValueError('review_settlement_odds_invalid')
    else:
        expected_fields = {'result_status', 'result_timestamp'}
        if original['result_status'] == 'withdrawn':
            expected_fields.add('withdrawn_car_numbers')
        if set(result) != expected_fields or result['result_status'] != original['result_status']:
            raise ValueError('review_nonstandard_confirmation_mismatch')
        if 'withdrawn_car_numbers' in expected_fields:
            withdrawn = result['withdrawn_car_numbers']
            if (not isinstance(withdrawn, list) or any(type(car) is not int for car in withdrawn) or
                    sorted(withdrawn) != sorted(original['withdrawn_car_numbers'])):
                raise ValueError('review_withdrawal_confirmation_mismatch')
    observed = _iso(result['result_timestamp'], 'evidence_result_timestamp')
    reviewed = _iso(decision['reviewed_at'], 'reviewed_at')
    if observed < _iso(original['result_timestamp'], 'held_result_timestamp') or reviewed < observed:
        raise ValueError('review_time_order_invalid')
    if result['result_status'] in ('normal', 'dead_heat') and observed < scheduled:
        raise ValueError('review_result_before_scheduled_start')
    return {
        'schema_version': REVIEW_SCHEMA, **SAFETY,
        'evaluation_eligible': False, 'hold_released': False,
        'release_requested': action == 'correct_declaration',
        'source_history_sha256': model_history._digest(source_history),
        'evidence_sha256': model_history._digest(evidence),
        'source_history': deepcopy(source_history), 'evidence': deepcopy(evidence),
        'decision': deepcopy(decision),
    }


def validate_review(receipt: dict, *, synthetic: bool = False) -> None:
    model_history._synthetic(synthetic)
    if not isinstance(receipt, dict) or receipt.get('schema_version') != REVIEW_SCHEMA:
        raise ValueError('review_schema_mismatch')
    expected = create_review(receipt.get('source_history'), receipt.get('evidence'), receipt.get('decision'), synthetic=True)
    if model_history._canonical(receipt) != model_history._canonical(expected):
        raise ValueError('review_receipt_mismatch')


def _result_key(receipt: dict) -> str:
    result = receipt['evidence']['result']
    return model_history._canonical({**result,
        'result_timestamp': _iso(result['result_timestamp'], 'result_timestamp').astimezone(timezone.utc).isoformat(),
        'settlement_odds': float(result['settlement_odds'])})


def evaluate_reviews(held_records: list[dict], reviews: list[dict], *, synthetic: bool = False) -> dict:
    """Release only fully reviewed, non-conflicting races in this supplied batch."""
    model_history._synthetic(synthetic)
    if not isinstance(held_records, list) or not isinstance(reviews, list):
        raise ValueError('review_lists_required')
    sources, groups, contexts = {}, defaultdict(list), {}
    for record in held_records:
        identity, scheduled, cars, engine = _hold(record)
        digest = model_history._digest(record)
        if digest in sources:
            continue
        sources[digest] = record
        key = model_history.race_key(identity)
        groups[key].append(digest)
        contexts[digest] = (identity, scheduled, cars, engine)
    by_source = defaultdict(dict)
    for receipt in reviews:
        validate_review(receipt, synthetic=True)
        digest = receipt['source_history_sha256']
        if digest not in sources:
            raise ValueError('review_source_not_in_batch')
        by_source[digest][model_history._digest(receipt)] = receipt

    cases, predictions = [], []
    for key, digests in sorted(groups.items()):
        identity = contexts[digests[0]][0]
        case = {'race_key': key, 'race_identity': deepcopy(identity),
                'held_history_sha256s': sorted(digests), 'hold_released': False,
                'disposition': 'unresolved', 'reason': None}
        context_keys = {(contexts[digest][1], tuple(contexts[digest][2])) for digest in digests}
        if len(context_keys) != 1:
            case['reason'] = 'conflicting_race_context'
        elif any(len(by_source[digest]) > 1 for digest in digests):
            case['reason'] = 'conflicting_reviews'
        elif any(not by_source[digest] for digest in digests):
            case['reason'] = 'unreviewed_held_history'
        else:
            receipts = [next(iter(by_source[digest].values())) for digest in digests]
            actions = {receipt['decision']['decision'] for receipt in receipts}
            if len(actions) != 1:
                case['reason'] = 'conflicting_review_decisions'
            elif actions == {'confirm_nonstandard'}:
                case.update(disposition='confirmed_excluded', reason='confirmed_nonstandard')
            elif len({_result_key(receipt) for receipt in receipts}) != 1:
                case['reason'] = 'conflicting_corrected_results'
            else:
                selected = []
                for engine in sorted({contexts[digest][3] for digest in digests}):
                    candidates = [sources[digest] for digest in digests if contexts[digest][3] == engine]
                    latest = max(_iso(record['prediction_timestamp'], 'prediction_timestamp') for record in candidates)
                    tied = [record for record in candidates if _iso(record['prediction_timestamp'], 'prediction_timestamp') == latest]
                    if len({model_history._digest(record['snapshot']) for record in tied}) != 1:
                        case['reason'] = 'conflicting_latest_snapshots'
                        break
                    selected.append((engine, min(tied, key=model_history._digest)))
                if case['reason'] is None:
                    result = receipts[0]['evidence']['result']
                    case.update(disposition='released_for_synthetic_review', hold_released=True,
                                reason='all_supplied_holds_corrected')
                    for engine, record in selected:
                        prediction = {'race_key': key, 'engine': engine,
                                      'source_history_sha256': model_history._digest(record),
                                      'prediction_timestamp': record['prediction_timestamp'],
                                      'outcome_combo': result['outcome_combo'],
                                      'metrics': score(_table(record, engine), result['outcome_combo'])}
                        if engine == 'ml':
                            prediction['model_artifact_sha256'] = record['model_artifact_sha256']
                        predictions.append(prediction)
        cases.append(case)
    fields = ('reciprocal_rank', 'log_loss', 'brier_sum', 'top1', 'top3', 'top5', 'top10')
    metrics_by_engine = {}
    for engine in ('phase32', 'ml'):
        rows = [row for row in predictions if row['engine'] == engine]
        metrics_by_engine[engine] = {
            'evaluated_races': len(rows),
            'metrics': {field: sum(row['metrics'][field] for row in rows) / len(rows) for field in fields} if rows else None,
        }
    return {
        'schema_version': REPORT_SCHEMA, **SAFETY,
        'scope': 'supplied_batch_synthetic_frozen_review_only',
        'status': 'completed_synthetic_review' if predictions else 'blocked_no_released_races',
        'probability_calibration_status': 'uncalibrated',
        'input_held_records': len(held_records), 'unique_held_records': len(sources),
        'duplicate_held_records': len(held_records) - len(sources),
        'input_reviews': len(reviews), 'unique_reviews': sum(map(len, by_source.values())),
        'released_races': sum(case['hold_released'] for case in cases),
        'confirmed_excluded_races': sum(case['disposition'] == 'confirmed_excluded' for case in cases),
        'unresolved_races': sum(case['disposition'] == 'unresolved' for case in cases),
        'cases': cases, 'predictions': predictions, 'metrics_by_engine': metrics_by_engine,
        'source_histories': deepcopy(held_records), 'reviews': deepcopy(reviews),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('create-review', 'evaluate'):
        command = commands.add_parser(name)
        command.add_argument('inputs', nargs=3 if name == 'create-review' else 1, type=Path)
        command.add_argument('--synthetic', action='store_true', help='Required: generated synthetic inputs only.')
        command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    model_history._synthetic(args.synthetic)
    values = [json.loads(path.read_text(encoding='utf-8')) for path in args.inputs]
    if args.command == 'create-review':
        result = create_review(*values, synthetic=True)
    else:
        batch = values[0]
        if not isinstance(batch, dict) or set(batch) != {'held_records', 'reviews'}:
            raise ValueError('review_batch_fields_invalid')
        result = evaluate_reviews(batch['held_records'], batch['reviews'], synthetic=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'schema_version': result['schema_version']}))
    return 2 if result.get('status') == 'blocked_no_released_races' else 0


if __name__ == '__main__':
    raise SystemExit(main())

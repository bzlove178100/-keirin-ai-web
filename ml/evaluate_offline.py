"""Chronological, paired offline evaluation; never promotes a model."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from itertools import permutations
import json
import math
from pathlib import Path
from typing import Any

from ml.build_training_dataset import load_records
from ml.dataset import rider_rows, supervised_eligibility
from ml.position_features import FEATURE_COLUMNS, row_to_features
from ml.predict_position_models import _position_distributions
from ml.train_position_models import _train_one
from ml.trifecta_adapter import combine_position_probabilities

BASELINE = 'phase32-hit-priority-all210-v1'


def timestamp(value: Any) -> float:
    if not isinstance(value, str):
        raise ValueError('timestamp_missing')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp_timezone_missing')
    return dt.timestamp()


def probability_table(rows: Any, cars: list[int]) -> dict[str, float]:
    expected = {'-'.join(map(str, p)) for p in permutations(cars, 3)}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('baseline_incomplete')
    values = {}
    for row in rows:
        key = row['combo_key']
        raw = row['estimated_probability']
        if key in values or key not in expected or isinstance(raw, bool):
            raise ValueError('baseline_invalid')
        p = float(raw)
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('baseline_invalid_probability')
        values[key] = p
    if abs(sum(values.values()) - 1) > 1e-6:
        raise ValueError('baseline_invalid_mass')
    return values


def prepare(records: list[dict], *, synthetic: bool = False) -> tuple[list[dict], dict]:
    excluded = Counter()
    candidates: dict[str, list[dict]] = {}
    for record in records:
        try:
            eligible, reason = supervised_eligibility(record)
            if not eligible:
                raise ValueError(reason)
            source = record['training_input'].get('prediction_context', {}).get('source', '')
            if 'synthetic' in str(source).lower() and not synthetic:
                raise ValueError('synthetic_excluded')
            race_id = str(record.get('race_id') or '').strip()
            if not race_id:
                raise ValueError('race_id_missing')
            pt = timestamp(record.get('prediction_timestamp'))
            rt = timestamp(record['metadata'].get('result_timestamp'))
            captured = timestamp(record['training_input'].get('captured_at'))
            if captured != pt or not pt < rt:
                raise ValueError('invalid_temporal_order')
            rows = rider_rows(record)
            raw_cars = [p['car_number'] for p in record['training_input']['players']]
            if any(isinstance(c, bool) or str(c) not in {str(i) for i in range(1, 10)} for c in raw_cars):
                raise ValueError('invalid_car_number')
            cars = [r['car_number'] for r in rows]
            if len(rows) != len(raw_cars) or len(set(cars)) != len(cars) or len(cars) != 7:
                raise ValueError('seven_unique_riders_required')
            if any(r['style'] not in {'逃', '両', '追'} for r in rows):
                raise ValueError('invalid_style')
            if record['metadata'].get('engine_version') != BASELINE:
                raise ValueError('baseline_version_mismatch')
            baseline = probability_table(record.get('trifecta_scores'), cars)
            if record['outcome_combo'] not in baseline:
                raise ValueError('outcome_not_in_riders')
            candidates.setdefault(race_id, []).append({
                'record': record, 'rows': rows, 'prediction_time': pt,
                'result_time': rt, 'baseline': baseline, 'race_id': race_id,
            })
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else 'malformed_record'
            excluded[reason] += 1
    selected = []
    duplicates = 0
    for group in candidates.values():
        outcomes = {x['record']['outcome_combo'] for x in group}
        if len(outcomes) != 1:
            excluded['conflicting_outcomes'] += len(group)
            continue
        latest = max(x['prediction_time'] for x in group)
        tied = [x for x in group if x['prediction_time'] == latest]
        if len({json.dumps(x['record'], sort_keys=True) for x in tied}) != 1:
            excluded['conflicting_latest_snapshots'] += len(group)
            continue
        selected.append(tied[0])
        duplicates += len(group) - 1
    selected.sort(key=lambda x: (x['prediction_time'], x['race_id']))
    matrix = [row_to_features(r) for x in selected for r in x['rows']]
    missing = {name: sum(not math.isfinite(row[i]) for row in matrix)
               for i, name in enumerate(FEATURE_COLUMNS)}
    return selected, {
        'input_records': len(records), 'eligible_unique_races': len(selected),
        'excluded': dict(excluded), 'duplicate_snapshots_removed': duplicates,
        'rider_rows': len(matrix), 'missing_feature_counts': missing,
        'missing_feature_fraction': {k: v / len(matrix) if matrix else None for k, v in missing.items()},
    }


def split_records(records: list[dict]) -> tuple[list[dict], list[dict], list[dict], dict]:
    # Keep simultaneous prediction timestamps in the same partition.
    times = sorted({x['prediction_time'] for x in records})
    if len(times) < 5:
        raise ValueError('need_at_least_five_distinct_prediction_times')
    valid_start = times[max(2, int(len(times) * 0.6))]
    test_start = times[max(3, int(len(times) * 0.8))]
    train = [x for x in records if x['prediction_time'] < valid_start and x['result_time'] < valid_start]
    valid = [x for x in records if valid_start <= x['prediction_time'] < test_start and x['result_time'] < test_start]
    test = [x for x in records if x['prediction_time'] >= test_start]
    if len(train) < 2 or not valid or not test:
        raise ValueError('insufficient_non_overlapping_partitions')
    return train, valid, test, {
        'train_race_ids': [x['race_id'] for x in train],
        'validation_race_ids': [x['race_id'] for x in valid],
        'test_race_ids': [x['race_id'] for x in test],
        'purged_unsettled_at_boundary': len(records) - len(train) - len(valid) - len(test),
        'validation_start': datetime.fromtimestamp(valid_start, timezone.utc).isoformat(),
        'test_start': datetime.fromtimestamp(test_start, timezone.utc).isoformat(),
    }


def score(table: dict[str, float], outcome: str) -> dict:
    ordered = sorted(table, key=lambda k: (-table[k], k))
    rank = ordered.index(outcome) + 1
    return {'rank': rank, 'reciprocal_rank': 1 / rank,
            'log_loss': -math.log(max(table[outcome], 1e-15)),
            'brier_sum': sum((p - int(k == outcome)) ** 2 for k, p in table.items()),
            **{f'top{k}': int(rank <= k) for k in (1, 3, 5, 10)}}


def evaluate_records(records: list[dict], *, synthetic: bool = False) -> dict:
    selected, quality = prepare(records, synthetic=synthetic)
    result = {
        'status': 'blocked_insufficient_eligible_data',
        'evaluation_version': 'offline-paired-holdout-v1',
        'evidence_scope': 'synthetic_test_only' if synthetic else 'provided_prospective_history_offline_holdout',
        'provenance_independently_verified': False,
        'production_prediction_enabled': False, 'db_write_enabled': False,
        'external_fetch_enabled': False, 'promotion_eligible': False,
        'monetary_ev_enabled': False, 'probability_calibration_status': 'uncalibrated',
        'data_quality': quality, 'baseline_version': BASELINE,
        'note': 'Technical checks do not prove timestamp authenticity, calibration, or live profitability. Holdout reuse requires a new untouched evaluation period.',
    }
    try:
        train, valid, test, split = split_records(selected)
    except ValueError as exc:
        result['blocked_reason'] = str(exc)
        return result
    models = {position: _train_one(
        [(x['race_id'], x['rows']) for x in train],
        [(x['race_id'], x['rows']) for x in valid], f'target_{position}')
        for position in ('first', 'second', 'third')}
    per_race = []
    for item in test:
        distributions = _position_distributions(models, item['rows'])
        table = combine_position_probabilities(*(distributions[p] for p in ('first', 'second', 'third')))
        candidate = {str(r['combo_key']): float(r['estimated_probability']) for r in table}
        outcome = item['record']['outcome_combo']
        per_race.append({'race_id': item['race_id'], 'candidate': score(candidate, outcome),
                         'baseline': score(item['baseline'], outcome)})
    fields = ['reciprocal_rank', 'log_loss', 'brier_sum', 'top1', 'top3', 'top5', 'top10']
    summary = {model: {key: sum(r[model][key] for r in per_race) / len(per_race) for key in fields}
               for model in ('candidate', 'baseline')}
    summary['candidate_minus_baseline'] = {k: summary['candidate'][k] - summary['baseline'][k] for k in fields}
    result.update(status='completed_offline_holdout', split=split, test_races=len(test),
                  metrics=summary, per_race=per_race)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_records(load_records(args.inputs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'data_quality': result['data_quality']}, ensure_ascii=False))
    return 0 if result['status'] == 'completed_offline_holdout' else 2


if __name__ == '__main__':
    raise SystemExit(main())

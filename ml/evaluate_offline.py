"""Chronological, paired offline evaluation; never promotes a model.

Record eligibility and chronological partitioning are imported from
``ml.evaluation_protocol`` so collection-readiness checks and the actual
LightGBM-vs-Phase32 evaluation cannot silently drift apart.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ml.build_training_dataset import load_records
from ml.evaluation_protocol import (
    BASELINE,
    prepare,
    probability_table,
    split_records,
    timestamp,
)
from ml.predict_position_models import _position_distributions
from ml.train_position_models import _train_one
from ml.trifecta_adapter import combine_position_probabilities


def score(table: dict[str, float], outcome: str) -> dict:
    ordered = sorted(table, key=lambda key: (-table[key], key))
    rank = ordered.index(outcome) + 1
    return {
        'rank': rank,
        'reciprocal_rank': 1 / rank,
        'log_loss': -math.log(max(table[outcome], 1e-15)),
        'brier_sum': sum((probability - int(key == outcome)) ** 2 for key, probability in table.items()),
        **{f'top{k}': int(rank <= k) for k in (1, 3, 5, 10)},
    }


def evaluate_records(records: list[dict], *, synthetic: bool = False) -> dict:
    selected, quality = prepare(records, synthetic=synthetic)
    result = {
        'status': 'blocked_insufficient_eligible_data',
        'evaluation_version': 'offline-paired-holdout-v1',
        'evidence_scope': 'synthetic_test_only' if synthetic else 'provided_prospective_history_offline_holdout',
        'provenance_independently_verified': False,
        'production_prediction_enabled': False,
        'db_write_enabled': False,
        'external_fetch_enabled': False,
        'promotion_eligible': False,
        'monetary_ev_enabled': False,
        'probability_calibration_status': 'uncalibrated',
        'data_quality': quality,
        'baseline_version': BASELINE,
        'protocol_source': 'ml.evaluation_protocol',
        'note': (
            'Technical checks do not prove timestamp authenticity, calibration, or live profitability. '
            'Holdout reuse requires a new untouched evaluation period.'
        ),
    }
    try:
        train, valid, test, split = split_records(selected)
    except ValueError as exc:
        result['blocked_reason'] = str(exc)
        return result

    models = {
        position: _train_one(
            [(item['race_id'], item['rows']) for item in train],
            [(item['race_id'], item['rows']) for item in valid],
            f'target_{position}',
        )
        for position in ('first', 'second', 'third')
    }

    per_race = []
    for item in test:
        distributions = _position_distributions(models, item['rows'])
        table = combine_position_probabilities(
            *(distributions[position] for position in ('first', 'second', 'third'))
        )
        candidate = {
            str(row['combo_key']): float(row['estimated_probability'])
            for row in table
        }
        outcome = item['record']['outcome_combo']
        per_race.append(
            {
                'race_id': item['race_id'],
                'candidate': score(candidate, outcome),
                'baseline': score(item['baseline'], outcome),
            }
        )

    fields = ['reciprocal_rank', 'log_loss', 'brier_sum', 'top1', 'top3', 'top5', 'top10']
    summary = {
        model: {
            key: sum(record[model][key] for record in per_race) / len(per_race)
            for key in fields
        }
        for model in ('candidate', 'baseline')
    }
    summary['candidate_minus_baseline'] = {
        key: summary['candidate'][key] - summary['baseline'][key]
        for key in fields
    }
    result.update(
        status='completed_offline_holdout',
        split=split,
        test_races=len(test),
        metrics=summary,
        per_race=per_race,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_records(load_records(args.inputs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
        encoding='utf-8',
    )
    print(json.dumps({'status': result['status'], 'data_quality': result['data_quality']}, ensure_ascii=False))
    return 0 if result['status'] == 'completed_offline_holdout' else 2


if __name__ == '__main__':
    raise SystemExit(main())

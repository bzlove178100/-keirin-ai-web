"""Offline synthetic FINAL 5 challenger, with a chronological second-stage holdout.

The fixed engineering objective is candidate win classification, not money or a
confirmed product rule. First-stage provenance is not independently verified.
The CLI has no network, live training, promotion or source-history writes.
An opt-in read-only Workbench companion can display saved model inference.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import re

from ml.category_selection import CATEGORY_RULES
from ml.final_five_preview import POLICY as BASELINE_POLICY
from ml.model_history import _canonical, _digest, _select_review_histories, _synthetic
from ml.model_web_response import model_web_response
from ml.settle_snapshot import _iso

SCHEMA = 'synthetic-final-five-ranker-v1'
POLICY = 'candidate_binary_lightgbm_v1'
FEATURES = ['estimated_probability', 'probability_rank', 'source_rank',
            'rider_count', 'candidate_count', *['category_' + c for c in CATEGORY_RULES]]
PARAMS = {'objective': 'binary', 'learning_rate': 0.05, 'num_leaves': 7,
          'max_depth': 3, 'min_data_in_leaf': 2, 'min_data_in_bin': 1,
          'seed': 42, 'num_threads': 2, 'deterministic': True,
          'force_col_wise': True, 'verbosity': -1}
ROUNDS = 40
LIMITS = {'synthetic_only': True, 'evidence_scope': 'synthetic_test_only',
          'production_prediction_enabled': False, 'external_fetch_enabled': False,
          'db_write_enabled': False, 'real_data_training_enabled': False,
          'monetary_ev_enabled': False, 'promotion_eligible': False,
          'provenance_independently_verified': False}


def candidate_matrix(snapshot):
    """Only frozen prediction fields enter features; never accept a settlement."""
    view = model_web_response(snapshot, snapshot['snapshot_sha256'][:32])
    candidates = [{**pick, 'source_rank': pick['rank'], 'source_category': key}
                  for key, group in view['categories'].items() for pick in group['picks']]
    candidates.sort(key=lambda p: (-p['estimated_probability'],
                                  tuple(map(int, p['combo_key'].split('-')))))
    if not 3 <= len(candidates) <= 15 or len({p['combo_key'] for p in candidates}) != len(candidates):
        raise ValueError('source_candidates_invalid')
    matrix = [[p['estimated_probability'], i + 1, p['source_rank'],
               view['quality']['rider_count'], len(candidates),
               *[int(p['source_category'] == c) for c in CATEGORY_RULES]]
              for i, p in enumerate(candidates)]
    return candidates, matrix


def _manifest(record, candidates):
    # The shared selector treats omitted and explicit normal status as equal.
    # Its arbitrary duplicate representative must not change the model identity.
    canonical = {**record, 'settlement': {**record['settlement'], 'result_status': 'normal'}}
    return {'race_id': record['race_id'], 'snapshot_sha256': record['snapshot']['snapshot_sha256'],
            'history_sha256': _digest(canonical), 'prediction_timestamp': record['prediction_timestamp'],
            'result_timestamp': record['settlement']['result_timestamp'],
            'candidate_count': len(candidates)}


def _partition(records, cutoff, synthetic):
    _synthetic(synthetic)
    boundary = _iso(cutoff, 'cutoff')
    if not isinstance(records, list):
        raise ValueError('history_list_required')
    selected, held, excluded, duplicates = _select_review_histories(records, synthetic=True)
    excluded = Counter(excluded)
    train, test = [], []
    for record in selected:
        if _iso(record['prediction_timestamp'], 'prediction_timestamp') >= boundary:
            test.append(record)
        elif _iso(record['settlement']['result_timestamp'], 'result_timestamp') < boundary:
            train.append(record)
        else:
            excluded['training_result_not_available_before_cutoff'] += 1
    return train, test, {'input_records': len(records), 'training_races': len(train),
                        'test_races': len(test), 'held_races': len(held),
                        'duplicate_snapshots_removed': duplicates, 'excluded': dict(excluded)}


def _load(artifact):
    """Native text model only; checksums detect damage, not trusted provenance."""
    import lightgbm as lgb
    keys = {'schema_version', 'policy', 'features', 'params', 'rounds', 'limits',
            'cutoff', 'training_manifest', 'lightgbm_version', 'model_text', 'sha256'}
    if not isinstance(artifact, dict) or set(artifact) != keys:
        raise ValueError('ranker_artifact_schema_invalid')
    if (artifact['schema_version'] != SCHEMA or artifact['policy'] != POLICY or
            artifact['features'] != FEATURES or artifact['params'] != PARAMS or
            type(artifact['rounds']) is not int or artifact['rounds'] != ROUNDS or
            _canonical(artifact['limits']) != _canonical(LIMITS)):
        raise ValueError('ranker_artifact_contract_mismatch')
    if artifact['sha256'] != _digest({k: v for k, v in artifact.items() if k != 'sha256'}):
        raise ValueError('ranker_artifact_digest_mismatch')
    boundary = _iso(artifact['cutoff'], 'cutoff')
    manifest = artifact['training_manifest']
    manifest_keys = {'race_id', 'snapshot_sha256', 'history_sha256', 'prediction_timestamp',
                     'result_timestamp', 'candidate_count'}
    if not isinstance(manifest, list) or len(manifest) < 5:
        raise ValueError('training_manifest_invalid')
    ids, times = set(), set()
    for row in manifest:
        if not isinstance(row, dict) or set(row) != manifest_keys:
            raise ValueError('training_manifest_invalid')
        if (not isinstance(row['race_id'], str) or not re.fullmatch('ml-race-[0-9a-f]{64}', row['race_id'])
                or row['race_id'] in ids or type(row['candidate_count']) is not int
                or not 3 <= row['candidate_count'] <= 15
                or any(not isinstance(row[k], str) or not re.fullmatch('[0-9a-f]{64}', row[k])
                       for k in ('snapshot_sha256', 'history_sha256'))):
            raise ValueError('training_manifest_invalid')
        prediction = _iso(row['prediction_timestamp'], 'prediction_timestamp')
        result = _iso(row['result_timestamp'], 'result_timestamp')
        if not prediction <= result < boundary:
            raise ValueError('training_manifest_time_order_invalid')
        ids.add(row['race_id']); times.add(prediction)
    if len(times) < 5:
        raise ValueError('five_training_times_required')
    text = artifact['model_text']
    if not isinstance(text, str) or not 1 <= len(text) <= 2_000_000:
        raise ValueError('ranker_model_text_invalid')
    model = lgb.Booster(model_str=text)
    if model.feature_name() != FEATURES or model.dump_model()['objective'].split()[0] != 'binary':
        raise ValueError('ranker_model_features_or_objective_mismatch')
    return model


def _predict(artifact, model, snapshot):
    import numpy as np
    candidates, matrix = candidate_matrix(snapshot)
    if snapshot['race_id'] in {r['race_id'] for r in artifact['training_manifest']}:
        raise ValueError('training_race_cannot_be_tested')
    if _iso(snapshot['captured_at'], 'captured_at') < _iso(artifact['cutoff'], 'cutoff'):
        raise ValueError('prediction_precedes_cutoff')
    scores = list(model.predict(np.asarray(matrix, dtype=float), num_threads=2))
    if len(scores) != len(candidates) or any(not math.isfinite(float(s)) for s in scores):
        raise ValueError('ranker_scores_invalid')
    order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i]),
                   -candidates[i]['estimated_probability'],
                   tuple(map(int, candidates[i]['combo_key'].split('-')))))
    return {'schema_version': 'synthetic-final-five-challenger-view-v1', **LIMITS,
            'selection_policy': POLICY, 'model_sha256': artifact['sha256'],
            'snapshot_sha256': snapshot['snapshot_sha256'], 'race_id': snapshot['race_id'],
            'rider_count': snapshot['prediction']['input_quality']['rider_count'],
            'candidate_count': len(candidates), 'selected_count': min(5, len(candidates)),
            'score_interpretation': 'uncalibrated_ranking_score_not_win_probability',
            'picks': [{**candidates[i], 'rank': rank + 1, 'ranking_score': float(scores[i])}
                      for rank, i in enumerate(order[:5])]}


def predict_ranker(artifact, snapshot, *, synthetic=False):
    _synthetic(synthetic)
    return _predict(artifact, _load(artifact), snapshot)


def run_experiment(records, cutoff, *, synthetic=False):
    """One fixed fit; test labels never enter training, tuning or early stopping."""
    train, test, counts = _partition(records, cutoff, synthetic)
    report = {'schema_version': 'synthetic-final-five-experiment-v1', **LIMITS,
              'evaluation_design': 'retrospective_second_stage_chronological_holdout',
              'first_stage_training_independence': 'not_independently_verified',
              'statistical_sufficiency': 'not_established', 'product_acceptance': False,
              'selection_policy': POLICY, 'baseline_policy': BASELINE_POLICY,
              'cutoff': cutoff, **counts, 'training_runs': 0, 'model_sha256': None,
              'strata': [], 'per_race': []}
    def blocked(reason):
        return {'model': None, 'report': {**report, 'status': reason}}
    if len({_iso(r['prediction_timestamp'], 'prediction_timestamp') for r in train}) < 5:
        return blocked('blocked_fewer_than_five_training_times')
    if not test:
        return blocked('blocked_no_test_races')
    matrix, labels, weights, manifest = [], [], [], []
    for record in train:
        candidates, rows = candidate_matrix(record['snapshot'])
        matrix.extend(rows)
        labels.extend(int(p['combo_key'] == record['settlement']['outcome_combo']) for p in candidates)
        # Keep races with an outside-pool winner (all negative), and give each
        # race total weight 1 regardless of its pool size.
        weights.extend([1 / len(candidates)] * len(candidates))
        manifest.append(_manifest(record, candidates))
    if len(set(labels)) != 2:
        return blocked('blocked_training_requires_both_labels')
    import lightgbm as lgb
    import numpy as np
    data = lgb.Dataset(np.asarray(matrix, dtype=float), label=labels, weight=weights, feature_name=FEATURES)
    model = lgb.train(deepcopy(PARAMS), data, num_boost_round=ROUNDS)
    artifact = {'schema_version': SCHEMA, 'policy': POLICY, 'features': list(FEATURES),
                'params': deepcopy(PARAMS), 'rounds': ROUNDS, 'limits': dict(LIMITS),
                'cutoff': cutoff, 'training_manifest': manifest,
                'lightgbm_version': lgb.__version__, 'model_text': model.model_to_string()}
    artifact['sha256'] = _digest(artifact)
    # Evaluate the reloaded representation, so persisted inference is exercised.
    loaded = _load(artifact)
    rows = []
    for record in test:
        view = _predict(artifact, loaded, record['snapshot'])
        candidates, _ = candidate_matrix(record['snapshot'])
        baseline = [p['combo_key'] for p in candidates[:5]]
        challenger = [p['combo_key'] for p in view['picks']]
        outcome = record['settlement']['outcome_combo']
        rows.append({'race_id': record['race_id'], 'snapshot_sha256': record['snapshot']['snapshot_sha256'],
                     'prediction_timestamp': record['prediction_timestamp'],
                     'rider_count': view['rider_count'], 'selected_count': len(baseline),
                     'candidate_count': len(candidates), 'baseline_combos': baseline,
                     'challenger_combos': challenger, 'baseline_hit': outcome in baseline,
                     'challenger_hit': outcome in challenger,
                     'candidate_pool_hit': any(p['combo_key'] == outcome for p in candidates)})
    strata = []
    for count in (7, 9):
        for size in (3, 4, 5):
            group = [r for r in rows if r['rider_count'] == count and r['selected_count'] == size]
            base, challenge = (sum(r[key] for r in group) for key in ('baseline_hit', 'challenger_hit'))
            strata.append({'rider_count': count, 'selected_count': size, 'races': len(group),
                           'baseline_hits': base, 'challenger_hits': challenge,
                           'baseline_hit_rate': base / len(group) if group else None,
                           'challenger_hit_rate': challenge / len(group) if group else None,
                           'challenger_only': sum(r['challenger_hit'] and not r['baseline_hit'] for r in group),
                           'baseline_only': sum(r['baseline_hit'] and not r['challenger_hit'] for r in group),
                           'both': sum(r['baseline_hit'] and r['challenger_hit'] for r in group),
                           'neither': sum(not r['baseline_hit'] and not r['challenger_hit'] for r in group),
                           'outside_pool': sum(not r['candidate_pool_hit'] for r in group)})
    report.update(status='completed_synthetic_second_stage_experiment', training_runs=1,
                  training_candidates=len(labels), training_positive_candidates=sum(labels),
                  model_sha256=artifact['sha256'], strata=strata, per_race=rows)
    return {'model': artifact, 'report': report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fit = commands.add_parser('fit'); fit.add_argument('histories', type=Path); fit.add_argument('--cutoff', required=True)
    predict = commands.add_parser('predict'); predict.add_argument('experiment', type=Path); predict.add_argument('snapshot', type=Path)
    for command in (fit, predict):
        command.add_argument('--synthetic', action='store_true', required=True)
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError('output_already_exists')
        if args.command == 'fit':
            result = run_experiment(json.loads(args.histories.read_text()), args.cutoff, synthetic=args.synthetic)
        else:
            result = predict_ranker(json.loads(args.experiment.read_text())['model'],
                                    json.loads(args.snapshot.read_text()), synthetic=args.synthetic)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(encoded)
        return 2 if args.command == 'fit' and result['model'] is None else 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())

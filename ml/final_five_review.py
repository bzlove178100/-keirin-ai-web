"""Retrospective synthetic diagnostic of the fixed FINAL 5 baseline.

No challenger training, policy tuning, future-performance claim or money metric.
The original category pool is a coverage bound, not an equal-budget competitor.
"""
import base64
import hashlib
from pathlib import Path
import re

from ml.final_five_preview import final_five_view, POLICY
from ml.model_history import _select_review_histories, SAFETY

SCHEMA = 'synthetic-final-five-review-v1'


def evaluate_final_five(records, *, synthetic=False):
    if not isinstance(records, list):
        raise ValueError('history_list_required')
    selected, held, excluded, duplicates = _select_review_histories(records, synthetic=synthetic)
    rows = []
    for record in selected:
        snapshot = record['snapshot']
        # This internal ID is derived from the frozen content, not a Workbench
        # link. Neither the selector nor its inputs receive settlement fields.
        view = final_five_view(snapshot, snapshot['snapshot_sha256'][:32])
        picks = [p['combo_key'] for p in view['picks']]
        pool = {p['combo_key'] for category in snapshot['prediction']['selected_predictions']['categories'].values()
                for p in category['picks']}
        outcome = record['settlement']['outcome_combo']
        hit = outcome in picks
        rows.append({
            'race_id': record['race_id'], 'race': view['race'],
            'rider_count': view['rider_count'], 'prediction_timestamp': record['prediction_timestamp'],
            'snapshot_sha256': snapshot['snapshot_sha256'],
            'candidate_count': len(pool), 'selected_count': len(picks), 'selected_combos': picks,
            'outcome_combo': outcome, 'selected_hit': hit, 'candidate_pool_hit': outcome in pool,
            'selected_rank': picks.index(outcome)+1 if hit else None,
            'diagnostic': 'selected_hit' if hit else 'removed_by_five' if outcome in pool else 'outside_pool',
        })
    def summary(group):
        return {'races': len(group), 'selected_hits': sum(r['selected_hit'] for r in group),
                'candidate_pool_hits': sum(r['candidate_pool_hit'] for r in group),
                'removed_by_five': sum(r['diagnostic'] == 'removed_by_five' for r in group),
                'outside_pool': sum(r['diagnostic'] == 'outside_pool' for r in group)}
    # Keep budgets and rider counts separate; no pooled 3/4/5-pick hit rate.
    strata = []
    for count in (7, 9):
        for size in (3, 4, 5):
            group = [r for r in rows if r['rider_count'] == count and r['selected_count'] == size]
            stats = summary(group)
            strata.append({'rider_count': count, 'selected_count': size, **stats,
                           'selected_hit_rate': stats['selected_hits']/len(group) if group else None})
    return {
        'schema_version': SCHEMA, **SAFETY, 'synthetic_only': True,
        'authentication_status': 'not_asserted', 'entitlement_status': 'not_asserted',
        'billing_enabled': False, 'second_stage_ai_enabled': False,
        'probability_calibration_status': 'uncalibrated', 'selection_policy': POLICY,
        'evaluation_design': 'retrospective_fixed_rule_diagnostic',
        'status': 'completed_synthetic_diagnostic' if rows else 'blocked_no_valid_histories',
        'input_records': len(records), 'evaluated_races': len(rows),
        'held_races': len(held), 'held_cases': sorted(held, key=lambda r: r['race_id']),
        'excluded': excluded, 'duplicate_snapshots_removed': duplicates,
        'summary': summary(rows), 'strata': strata, 'per_race': rows,
    }


def render_final_five_review():
    html = (Path(__file__).parent/'templates'/'final_five_review.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    return html, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()

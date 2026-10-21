"""Read-only FINAL 5 comparison baseline for frozen synthetic candidates.

This is a probability-only baseline for a future second-stage selector, not
that selector, a membership authority, or a validated betting recommendation.
"""
import base64
import hashlib
import json
from pathlib import Path
import re

from ml.model_web_response import model_web_response

SCHEMA = 'synthetic-final-five-baseline-v1'
POLICY = 'existing_category_probability_desc_combo_asc_v1'


def final_five_view(snapshot, snapshot_id):
    # Validates provenance, complete probabilities and exact original category
    # selection before projecting. Never rank the full 210/504 combinations.
    full = model_web_response(snapshot, snapshot_id)
    candidates = []
    for key, category in full['categories'].items():
        for pick in category['picks']:
            candidates.append({
                'combo_key': pick['combo_key'],
                'estimated_probability': pick['estimated_probability'],
                'odds': pick['odds'], 'source_category': key,
                'source_category_name': category['category_name'],
                'source_rank': pick['rank'],
            })
    # The existing selector already enforces cross-category uniqueness.
    # Refuse an inconsistent upstream result instead of hiding the problem.
    if len({p['combo_key'] for p in candidates}) != len(candidates) or len(candidates) > 15:
        raise ValueError('source_candidates_invalid')
    candidates.sort(key=lambda p: (-p['estimated_probability'], tuple(map(int, p['combo_key'].split('-')))))
    picks = [{'rank': index+1, **pick} for index, pick in enumerate(candidates[:5])]
    return {
        'schema_version': SCHEMA, 'scope': 'synthetic_final_five_baseline',
        'synthetic_only': True, 'authentication_status': 'not_asserted',
        'entitlement_status': 'not_asserted', 'billing_enabled': False,
        'production_prediction_enabled': False, 'db_write_enabled': False,
        'external_fetch_enabled': False, 'supervised_training_enabled': False,
        'monetary_ev_enabled': False, 'second_stage_ai_enabled': False,
        'probability_calibration_status': 'uncalibrated',
        'selection_policy': POLICY, 'source_selection_policy': full['selection_policy'],
        'snapshot_id': snapshot_id, 'captured_at': full['captured_at'],
        'race': full['race'], 'rider_count': full['quality']['rider_count'],
        'candidate_count': len(candidates), 'selected_count': len(picks),
        'shortfall': 5-len(picks), 'status': 'ready' if len(picks) == 5 else 'partial',
        'picks': picks,
    }


def render_final_five_preview(snapshot_id):
    if not isinstance(snapshot_id, str) or not re.fullmatch('[0-9a-f]{32}', snapshot_id):
        raise ValueError('snapshot_id_invalid')
    html = (Path(__file__).parent/'templates'/'final_five_preview.html').read_text(encoding='utf-8')
    html = html.replace('/* SNAPSHOT_ID */', json.dumps(snapshot_id))
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return html, digest

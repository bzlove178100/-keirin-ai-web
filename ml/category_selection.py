"""Offline ML adapter for the existing Phase32 five-category selection policy.

Only selection is reused: no Phase32 weighted scores or explanatory reasons.
Parity with the original TypeScript selector is checked on generated ML tables.
"""
from __future__ import annotations

from itertools import permutations
import math
from typing import Any

CATEGORY_RULES = {
    'hit_priority': ('的中率優先', None, None),
    'balance': ('穴＋バランス', 20, 60),
    'middle': ('中穴', 60, 100),
    'longshot': ('大穴', 100, 500),
    'super_longshot': ('超大穴', 500, None),
}
SELECTION_POLICY = 'hit_priority_all_combos_odds_bands_probability_uncalibrated_v2'


def _number(value: Any, *, probability: bool = False) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and (
        0 <= value <= 1 if probability else value > 0
    )


def validate_model_scores(rows: Any, rider_count: int) -> int:
    if type(rider_count) is not int or rider_count not in (7, 9):
        raise ValueError('standard seven or nine riders required')
    expected = {'-'.join(map(str, c)) for c in permutations(range(1, rider_count + 1), 3)}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('complete probability table required')
    seen, mass, known = set(), 0.0, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid probability row')
        key, p, odds = row.get('combo_key'), row.get('estimated_probability'), row.get('odds')
        if not isinstance(key, str) or key not in expected or key in seen or not _number(p, probability=True):
            raise ValueError('invalid probability row')
        if 'combo' in row and (not isinstance(row['combo'], list) or
                any(type(car) is not int for car in row['combo']) or
                row['combo'] != list(map(int, key.split('-')))):
            raise ValueError('combo does not match combo_key')
        if odds is not None and not _number(odds):
            raise ValueError('invalid confirmed odds')
        if row.get('monetary_expected_value') is not None:
            raise ValueError('monetary EV must remain unavailable')
        if any(field in row for field in ('score', 'contributions', 'reason',
                                         'expected_value_index', 'uncalibrated_odds_probability_product')):
            raise ValueError('Phase32 scores, explanations and EV fields are not ML output')
        seen.add(key)
        mass += p
        known += odds is not None
    if abs(mass - 1) > 1e-6:
        raise ValueError('probability mass must equal one')
    return known


def select_model_categories(rows: list[dict], rider_count: int) -> dict:
    known_count = validate_model_scores(rows, rider_count)
    # Python and modern JS sort are stable. ML has no Phase32 `score` tie-breaker.
    ranked = sorted(rows, key=lambda row: -row['estimated_probability'])
    used: set[str] = set()
    categories = {}
    for key, (name, minimum, maximum) in CATEGORY_RULES.items():
        hit = key == 'hit_priority'
        eligible = ranked if hit else [row for row in ranked if
            row['combo_key'] not in used and row.get('odds') is not None and
            (minimum is None or row['odds'] >= minimum) and
            (maximum is None or row['odds'] < maximum)]
        picks = []
        for row in eligible[:3]:
            used.add(row['combo_key'])
            picks.append({**row, 'rank': len(picks) + 1, 'category': key,
                          'category_name': name, 'fallback': False, 'category_note': None})
        size = len(picks)
        note = None
        if size < 3:
            note = ('3連単オッズ未取得のため見送り' if not known_count else
                    f'確認済みデータ内の候補が不足しているため{size}点。未確認オッズでは補完しません。')
        categories[key] = {
            'category_name': name,
            'candidate_scope': 'all_combinations' if hit else 'confirmed_odds_only',
            'status': 'ready' if size == 3 else 'partial' if size else 'skipped',
            'available_candidates': len(eligible), 'picks': picks, 'category_note': note,
        }
    return {
        'selection_policy': SELECTION_POLICY,
        'probability_calibration_status': 'uncalibrated', 'monetary_ev_enabled': False,
        'odds_band_ranking': 'estimated_probability_only', 'odds_available': known_count > 0,
        'known_odds_count': known_count, 'categories': categories,
        'total_picks': len(used), 'unique_picks': len(used),
        'complete_category_count': sum(len(c['picks']) == 3 for c in categories.values()),
        'insufficient_categories': [key for key, c in categories.items() if len(c['picks']) < 3],
    }

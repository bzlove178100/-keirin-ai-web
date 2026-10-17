"""Self-contained, network-free display of an existing offline prediction."""
from __future__ import annotations

from html import escape
from itertools import permutations
import math
from pathlib import Path
from string import Template
from typing import Any

POSITIONS = ('first', 'second', 'third')


def _number(value: Any, *, probability: bool = False) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and (
        0 <= value <= 1 if probability else value > 0
    )


def validate_preview(result: Any) -> None:
    if not isinstance(result, dict) or result.get('success') is not True:
        raise ValueError('successful offline inference result required')
    expected = {
        'mode': 'offline_inference_only', 'model_version': 'lightgbm-position-rankers-v1',
        'inference_version': 'lightgbm-offline-inference-v1',
        'adapter_version': 'position-probability-to-trifecta-v1',
        'probability_calibration_status': 'uncalibrated',
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError('offline result version or calibration mismatch')
    for key in ('production_prediction_enabled', 'db_write_enabled',
                'external_fetch_enabled', 'monetary_ev_enabled', 'odds_used_as_model_feature'):
        if result.get(key) is not False:
            raise ValueError(f'{key} must be false')
    quality = result.get('input_quality')
    if not isinstance(quality, dict):
        raise ValueError('input quality required')
    count = quality.get('rider_count')
    if type(count) is not int or count not in (7, 9):
        raise ValueError('standard seven or nine riders required')
    cars = set(range(1, count + 1))
    expected_keys = {'-'.join(map(str, xs)) for xs in permutations(sorted(cars), 3)}
    scores = result.get('trifecta_scores')
    if not isinstance(scores, list) or len(scores) != len(expected_keys):
        raise ValueError('complete probability table required')
    seen, mass, known = set(), 0.0, 0
    for row in scores:
        if not isinstance(row, dict):
            raise ValueError('invalid probability row')
        key, p, odds = row.get('combo_key'), row.get('estimated_probability'), row.get('odds')
        if not isinstance(key, str) or key not in expected_keys or key in seen or not _number(p, probability=True):
            raise ValueError('invalid probability row')
        if odds is not None and not _number(odds):
            raise ValueError('invalid confirmed odds')
        if row.get('monetary_expected_value') is not None:
            raise ValueError('monetary EV must remain unavailable')
        seen.add(key)
        mass += p
        known += odds is not None
    if abs(mass - 1) > 1e-6:
        raise ValueError('probability mass must equal one')
    if (type(quality.get('possible_trifecta_count')) is not int or
            quality['possible_trifecta_count'] != len(expected_keys) or
            type(quality.get('known_trifecta_odds_count')) is not int or
            quality['known_trifecta_odds_count'] != known):
        raise ValueError('coverage metadata does not match probability table')
    rankings = result.get('position_rankings')
    if not isinstance(rankings, dict):
        raise ValueError('position rankings required')
    for position in POSITIONS:
        rows = rankings.get(position)
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError('complete position rankings required')
        seen, mass = set(), 0.0
        for rank, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError('invalid position row')
            car, p = row.get('car_number'), row.get('estimated_probability')
            if (type(car) is not int or car not in cars or car in seen or
                    type(row.get('rank')) is not int or row['rank'] != rank or not _number(p, probability=True)):
                raise ValueError('invalid position row')
            seen.add(car)
            mass += p
        if abs(mass - 1) > 1e-6:
            raise ValueError('position probability mass must equal one')


def _safe(value: Any) -> str:
    return escape(str(value) if value is not None else '未設定', quote=True)


def _table(rows: list[dict], *, positions: bool = False) -> str:
    body = []
    for rank, row in enumerate(rows, start=1):
        combo = str(row['car_number']) + '番' if positions else row['combo_key']
        odds = '' if positions else '<td>' + (f"{row['odds']:,.1f}倍" if row['odds'] is not None else '未確認') + '</td>'
        body.append(f'<tr><td>{rank}</td><td class="combo">{_safe(combo)}</td><td>{row["estimated_probability"]*100:.3f}%</td>{odds}</tr>')
    return ('<div class="table-wrap"><table><thead><tr><th>順位</th><th>' +
            ('車番' if positions else '3連単') + '</th><th>未校正スコア</th>' +
            ('' if positions else '<th>予測時オッズ</th>') +
            '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>')


def render_preview(result: dict[str, Any]) -> str:
    validate_preview(result)
    quality = result['input_quality']
    race = result.get('race') if isinstance(result.get('race'), dict) else {}
    metadata = result.get('model_artifact')
    metadata = metadata if isinstance(metadata, dict) else {}
    scope = '合成データでの動作検証' if metadata.get('evidence_scope') == 'synthetic_test_only' else '学習データの由来は未確認'
    ranked = sorted(result['trifecta_scores'], key=lambda r: (-r['estimated_probability'], tuple(map(int, r['combo_key'].split('-')))))
    cards = ''.join(f'<section class="card"><h3>{i}着モデル</h3>{_table(result["position_rankings"][position], positions=True)}</section>' for i, position in enumerate(POSITIONS, start=1))
    template = Template((Path(__file__).parent / 'templates' / 'offline_preview.html').read_text(encoding='utf-8'))
    return template.substitute(
        title=f"{_safe(race.get('venue'))} {_safe(race.get('race_number'))}R",
        race_date=_safe(race.get('date')), scope=scope, count=quality['rider_count'],
        possible=quality['possible_trifecta_count'], known=quality['known_trifecta_odds_count'],
        top_table=_table(ranked[:10]), position_cards=cards, full_table=_table(ranked),
        model_version=_safe(result['model_version']), generated_at=_safe(result.get('generated_at')),
    )

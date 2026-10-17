"""Self-contained, network-free display of an existing offline prediction."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
from string import Template
from typing import Any

from ml.category_selection import CATEGORY_RULES, _number, select_model_categories, validate_model_scores
from ml.race_conditions import require_standard_conditions

POSITIONS = ('first', 'second', 'third')


def validate_preview(result: Any) -> None:
    if not isinstance(result, dict) or result.get('success') is not True:
        raise ValueError('successful offline inference result required')
    if 'race_conditions' in result:
        require_standard_conditions(result['race_conditions'])
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
    scores = result.get('trifecta_scores')
    known = validate_model_scores(scores, count)
    if (type(quality.get('possible_trifecta_count')) is not int or
            quality['possible_trifecta_count'] != len(scores) or
            type(quality.get('known_trifecta_odds_count')) is not int or
            quality['known_trifecta_odds_count'] != known):
        raise ValueError('coverage metadata does not match probability table')
    # Older preview JSON can still be viewed. If supplied, selection must exactly
    # match the model table; never display stale or substituted category picks.
    if 'selected_predictions' in result:
        expected_selection = select_model_categories(scores, count)
        if json.dumps(result['selected_predictions'], sort_keys=True, allow_nan=False) != json.dumps(expected_selection, sort_keys=True, allow_nan=False):
            raise ValueError('category selection does not match model table')
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
    selection = select_model_categories(result['trifecta_scores'], quality['rider_count'])
    category_cards = []
    for key, category in selection['categories'].items():
        _, minimum, maximum = CATEGORY_RULES[key]
        band = ('全組合せからスコア順' if key == 'hit_priority' else
                f'{minimum}倍以上' + (f'・{maximum}倍未満' if maximum is not None else ''))
        status = {'ready': '3点', 'partial': f"{len(category['picks'])}点・候補不足", 'skipped': '見送り'}[category['status']]
        content = _table(category['picks']) if category['picks'] else ''
        note = f'<p class="muted">{_safe(category["category_note"])}</p>' if category['category_note'] else ''
        category_cards.append(f'<section class="card category" data-category="{key}"><h3>{_safe(category["category_name"])} <span class="muted">{status}</span></h3><p class="muted">{band}</p>{content}{note}</section>')
    template = Template((Path(__file__).parent / 'templates' / 'offline_preview.html').read_text(encoding='utf-8'))
    return template.substitute(
        title=f"{_safe(race.get('venue'))} {_safe(race.get('race_number'))}R",
        race_date=_safe(race.get('date')), scope=scope, count=quality['rider_count'],
        possible=quality['possible_trifecta_count'], known=quality['known_trifecta_odds_count'],
        top_table=_table(ranked[:10]), position_cards=cards, full_table=_table(ranked),
        category_cards=''.join(category_cards), total_picks=selection['total_picks'],
        model_version=_safe(result['model_version']), generated_at=_safe(result.get('generated_at')),
    )

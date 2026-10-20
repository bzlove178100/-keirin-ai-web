"""Synthetic category-disclosure rehearsal, never a membership authority.

The local demo deliberately lets visitors select every fixture. No fixture may
be accepted as an authenticated entitlement by a production API.
"""
from datetime import datetime, timedelta
import base64
import hashlib
import json
from pathlib import Path
import re

from ml.model_web_response import model_web_response
from ml.settle_snapshot import CATEGORIES, _iso

SCHEMA = 'synthetic-category-view-v1'
GRANT_SCHEMA = 'synthetic-category-fixture-v1'
SCENARIOS = ('none', 'hit', 'two', 'three', 'all', 'expired', 'future', 'other-snapshot')


def _key(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('snapshot_id_invalid')


def category_view(snapshot, snapshot_id, grant, *, now):
    """Project only the supplied synthetic fixture's categories, without writes."""
    _key(snapshot_id)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError('aware_clock_required')
    response = {'schema_version': SCHEMA, 'scope': 'synthetic_category_disclosure_test',
                'synthetic_only': True, 'authentication_status': 'not_asserted',
                'entitlement_status': 'not_asserted', 'billing_enabled': False,
                'production_prediction_enabled': False, 'db_write_enabled': False,
                'external_fetch_enabled': False, 'supervised_training_enabled': False,
                'monetary_ev_enabled': False, 'probability_calibration_status': 'uncalibrated',
                'status': 'locked', 'reason': 'no_categories', 'categories': {},
                'locked_categories': list(CATEGORIES), 'total_picks': 0}
    if grant is None:
        return response
    if (not isinstance(grant, dict) or set(grant) != {
            'schema_version', 'synthetic_only', 'snapshot_id', 'categories', 'starts_at', 'ends_at'} or
            grant['schema_version'] != GRANT_SCHEMA or grant['synthetic_only'] is not True):
        raise ValueError('synthetic_category_fixture_required')
    _key(grant['snapshot_id'])
    categories = grant['categories']
    if (not isinstance(categories, list) or len(categories) > len(CATEGORIES) or
            any(not isinstance(key, str) or key not in CATEGORIES for key in categories) or
            len(set(categories)) != len(categories)):
        raise ValueError('fixture_categories_invalid')
    starts, ends = _iso(grant['starts_at'], 'starts_at'), _iso(grant['ends_at'], 'ends_at')
    if starts >= ends:
        raise ValueError('fixture_time_range_invalid')
    if grant['snapshot_id'] != snapshot_id:
        return {**response, 'reason': 'different_snapshot'}
    if now < starts:
        return {**response, 'reason': 'not_started'}
    if now >= ends:
        return {**response, 'reason': 'expired'}
    if not categories:
        return response
    # Use the existing frozen-snapshot validator and allowlisted display fields.
    # Never send the all-category response to the browser and hide it there.
    full = model_web_response(snapshot, snapshot_id)
    visible = {key: full['categories'][key] for key in CATEGORIES if key in categories}
    return {**response, 'status': 'visible', 'reason': 'synthetic_fixture_only',
            'snapshot_id': snapshot_id, 'race': full['race'], 'captured_at': full['captured_at'],
            'rider_count': full['quality']['rider_count'], 'categories': visible,
            'locked_categories': [key for key in CATEGORIES if key not in visible],
            'total_picks': sum(len(value['picks']) for value in visible.values())}


def fixture_view(snapshot, snapshot_id, scenario, *, now):
    """Only these server-generated demo cases are reachable from the local UI."""
    if scenario not in SCENARIOS:
        raise ValueError('unknown_category_fixture')
    if scenario == 'none':
        return category_view(snapshot, snapshot_id, None, now=now)
    count = {'hit': 1, 'two': 2, 'three': 3}.get(scenario, 5)
    starts, ends = now-timedelta(minutes=1), now+timedelta(minutes=1)
    if scenario == 'expired': starts, ends = now-timedelta(minutes=2), now
    if scenario == 'future': starts, ends = now+timedelta(minutes=1), now+timedelta(minutes=2)
    other = 'f'*32 if snapshot_id != 'f'*32 else 'e'*32
    grant = {'schema_version': GRANT_SCHEMA, 'synthetic_only': True,
             'snapshot_id': other if scenario == 'other-snapshot' else snapshot_id,
             'categories': list(CATEGORIES[:count]), 'starts_at': starts.isoformat(), 'ends_at': ends.isoformat()}
    return category_view(snapshot, snapshot_id, grant, now=now)


def render_category_preview(snapshot_id):
    _key(snapshot_id)
    html = (Path(__file__).parent/'templates'/'product_category_preview.html').read_text(encoding='utf-8')
    html = html.replace('/* SNAPSHOT_ID */', json.dumps(snapshot_id))
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return html, digest

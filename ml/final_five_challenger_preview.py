"""Read-only, opt-in display of an already fitted synthetic FINAL 5 model."""
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from ml.final_five_preview import final_five_view
from ml.final_five_ranker import LIMITS, POLICY, _load, _predict
from ml.settle_snapshot import _iso

MAX_BYTES = 8 * 1024 * 1024
SCHEMA = 'synthetic-final-five-comparison-v1'


class FrozenChallenger:
    """Pin a validated native model for this process; never fit or hot-reload."""
    def __init__(self, experiment_path=None):
        self.artifact = self.model = None
        if experiment_path is None:
            return
        fd = os.open(experiment_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError('challenger_file_invalid')
            raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('challenger_file_too_large')
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {'model', 'report'} or value['model'] is None:
            raise ValueError('challenger_experiment_requires_model')
        # The report is deliberately not trusted, rendered or used in inference.
        # Only the existing strict model contract is accepted.
        self.artifact = deepcopy(value['model'])
        self.model = _load(self.artifact)

    def view(self, snapshot, snapshot_id, *, held=False, storage=None):
        baseline = final_five_view(snapshot, snapshot_id)
        response = {'schema_version': SCHEMA, **LIMITS,
                    'scope': 'synthetic_final_five_comparison', 'snapshot_id': snapshot_id,
                    'authentication_status': 'not_asserted', 'entitlement_status': 'not_asserted',
                    'billing_enabled': False, 'training_on_request': False, 'product_acceptance': False,
                    'baseline': baseline, 'challenger': None, 'model': None,
                    'storage': storage, 'status': 'blocked', 'blocked_reason': None}
        if self.artifact is None:
            response['blocked_reason'] = 'model_not_configured'
            return response
        artifact = self.artifact
        response['model'] = {'sha256': artifact['sha256'], 'cutoff': artifact['cutoff'],
                             'selection_policy': POLICY, 'loading_policy': 'pinned_at_process_start'}
        if held:
            response['blocked_reason'] = 'held_race_requires_review'
        elif snapshot['race_id'] in {r['race_id'] for r in artifact['training_manifest']}:
            response['blocked_reason'] = 'training_race_cannot_be_tested'
        elif _iso(snapshot['captured_at'], 'captured_at') < _iso(artifact['cutoff'], 'cutoff'):
            response['blocked_reason'] = 'prediction_precedes_cutoff'
        else:
            predicted = _predict(artifact, self.model, snapshot)
            # Project only display fields. No model text, manifest or outcome.
            response['challenger'] = {
                'selected_count': predicted['selected_count'],
                'score_interpretation': predicted['score_interpretation'],
                'picks': [{k: p[k] for k in ('rank', 'combo_key', 'estimated_probability', 'odds',
                                           'source_category', 'source_rank', 'ranking_score')}
                          for p in predicted['picks']]}
            response['status'] = 'ready'
        return response


def render_challenger_preview(snapshot_id):
    if not isinstance(snapshot_id, str) or not re.fullmatch('[0-9a-f]{32}', snapshot_id):
        raise ValueError('snapshot_id_invalid')
    html = (Path(__file__).parent/'templates'/'final_five_challenger.html').read_text(encoding='utf-8')
    html = html.replace('/* SNAPSHOT_ID */', json.dumps(snapshot_id))
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    return html, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()

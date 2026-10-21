"""Read-only snapshot of one explicitly selected local synthetic experiment ledger."""
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from ml.final_five_experiment_ledger import LIMITATIONS, summarize_payload, validate_payload
from ml.model_history import _digest
from ml.synthetic_session import MAX_BYTES, SessionSaveError

SCHEMA = 'synthetic-final-five-experiment-audit-view-v1'
DISPLAY_LIMITS = {**LIMITATIONS, 'read_only': True, 'training_on_request': False,
                  'model_match_basis': 'saved_model_sha256_only_not_provenance',
                  'loading_policy': 'pinned_checkpoint_with_change_refusal'}


class FrozenExperimentAudit:
    """No lock creation or writes. Checkpoint replacement requires a new reader."""
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.payload = self.expected = None
        self.failed = False
        if self.path is None:
            return
        if self.path.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('experiment_audit_must_be_outside_repository')
        self.expected = self._read()
        envelope = json.loads(self.expected)
        if (not isinstance(envelope, dict) or set(envelope) != {'payload', 'sha256'} or
                envelope['sha256'] != _digest(envelope['payload'])):
            raise ValueError('experiment_audit_envelope_invalid')
        validate_payload(envelope['payload'])
        self.payload = deepcopy(envelope['payload'])

    def _read(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError('experiment_audit_file_invalid')
            data = handle.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('experiment_audit_file_too_large')
        return data

    def view(self):
        if self.failed:
            raise SessionSaveError('experiment_audit_restart_required')
        response = {'schema_version': SCHEMA, **DISPLAY_LIMITS,
                    'configured': self.path is not None, 'revision': None, 'attempts': [],
                    'overlap_basis': 'all_prior_registrations_including_failed_or_unrun'}
        if self.path is None:
            return response
        try:
            if self._read() != self.expected:
                raise ValueError('experiment_audit_changed')
        except (ValueError, OSError) as exc:
            self.failed = True
            raise SessionSaveError('experiment_audit_changed_restart_required') from exc
        summary = summarize_payload(self.payload, True)
        rows = []
        for row, source in zip(summary['attempts'], self.payload['attempts']):
            rows.append({**row, **{k: source[k] for k in ('started_at', 'finished_at', 'terminal_reason')},
                         'eligibility': source['plan']['eligibility'],
                         'counts': source['plan']['counts'],
                         'strata': source['result']['report']['strata'] if source['status'] == 'completed' else None})
        # Never expose raw histories, native model text, per-race outcomes or
        # arbitrarily trusted report fields; all data was validated on startup.
        response.update(revision=summary['revision'], attempts=rows)
        return deepcopy(response)


def render_experiment_preview(mode='all', key=None):
    if mode not in ('all', 'model', 'attempt'):
        raise ValueError('experiment_audit_filter_invalid')
    if mode == 'all':
        if key is not None:
            raise ValueError('experiment_audit_filter_invalid')
    elif not isinstance(key, str) or not re.fullmatch('[0-9a-f]{%d}' % (64 if mode == 'model' else 32), key):
        raise ValueError('experiment_audit_filter_invalid')
    html = (Path(__file__).parent/'templates'/'final_five_experiments.html').read_text(encoding='utf-8')
    html = html.replace('/* INITIAL_FILTER */', json.dumps({'mode': mode, 'key': key}))
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    return html, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()

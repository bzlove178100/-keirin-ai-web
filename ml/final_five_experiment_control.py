"""Explicit synthetic-only operations using the existing local experiment ledger.

HTTP serializes these synchronous operations with the Workbench lock. A live
fit cannot be cancelled by abandon; after process loss, running stays unknown.
"""
import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from ml.final_five_experiment_ledger import ExperimentLedger, LIMITATIONS, TERMINAL, _id
from ml.final_five_experiment_preview import audit_view
from ml.model_history import _digest
from ml.synthetic_session import SessionSaveError, validate_session

SCHEMA = 'synthetic-final-five-experiment-control-v1'


class ExperimentConflict(ValueError):
    pass


class ExperimentControl:
    def __init__(self, app, directory):
        self.app = app
        self.ledger = ExperimentLedger(directory, synthetic=True)

    def close(self):
        self.ledger.close()

    def _source(self):
        store = self.app.store
        if store is not None:
            if store.failed:
                raise SessionSaveError('prediction_session_restart_required')
            try:
                if store._read() != store.expected:
                    raise ValueError('prediction_session_changed')
            except (ValueError, OSError) as exc:
                store.failed = True
                raise SessionSaveError('prediction_session_changed_restart_required') from exc
        validate_session(self.app._payload())
        return deepcopy([r for _, r in sorted(self.app.histories.items())])

    def audit(self):
        with self.ledger.lock:
            self.ledger._current()
            view = audit_view(self.ledger.payload)
            view['loading_policy'] = 'owned_ledger_current_checkpoint'
            return view

    def state(self):
        records = self._source()
        return {'schema_version': SCHEMA, **LIMITATIONS, 'configured': True,
                'explicit_synthetic_training_enabled': True, 'model_switch_enabled': False,
                'execution_mode': 'synchronous_serialized_no_live_cancel',
                'source': {'revision': _digest(records), 'histories': len(records),
                           'cutoffs': sorted({r['snapshot']['captured_at'] for r in records})},
                'audit': self.audit()}

    def _revision(self, revision):
        if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
            raise ValueError('experiment_revision_invalid')
        self.ledger._current()
        if revision != _digest(self.ledger.payload):
            raise ExperimentConflict('experiment_revision_changed')

    def register(self, attempt_id, reason, cutoff, retry_of, source_revision, revision):
        records = self._source()
        if source_revision != _digest(records):
            raise ExperimentConflict('experiment_source_changed')
        _id(attempt_id)
        with self.ledger.lock:
            self.ledger._current()
            # A duplicate ID is still checked against its original conditions.
            if not any(r['attempt_id'] == attempt_id for r in self.ledger.payload['attempts']):
                self._revision(revision)
            self.ledger.register(records, cutoff, attempt_id, reason, retry_of=retry_of)
        return self.state()

    def run(self, attempt_id, revision):
        with self.ledger.lock:
            self.ledger._current(); row = self.ledger._row(attempt_id)
            if row['status'] not in TERMINAL:
                self._revision(revision)
                if row['input_sha256'] != _digest(self._source()):
                    raise ExperimentConflict('experiment_source_changed_before_run')
            self.ledger.run(attempt_id)
        return self.state()

    def abandon(self, attempt_id, reason, revision):
        with self.ledger.lock:
            self.ledger._current(); row = self.ledger._row(attempt_id)
            if not (row['status'] == 'interrupted' and row['terminal_reason'] == reason):
                self._revision(revision)
            self.ledger.abandon(attempt_id, reason)
        return self.state()


def unconfigured_state():
    return {'schema_version': SCHEMA, **LIMITATIONS, 'configured': False,
            'explicit_synthetic_training_enabled': False, 'model_switch_enabled': False,
            'execution_mode': 'synchronous_serialized_no_live_cancel', 'source': None, 'audit': None}


def render_experiment_control():
    root = Path(__file__).parent/'templates'
    html = (root/'final_five_experiment_control.html').read_text()
    html = html.replace('/* SHARED_VALIDATION */', (root/'final_five_experiment_validation.js').read_text())
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    return html, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()

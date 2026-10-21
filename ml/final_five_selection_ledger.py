"""Local synthetic FINAL 5 selection receipts, never training or promotion.

Append-only through this API; not a signed, global, or rollback-proof ledger.
Records preserve the model and snapshot so restoration can recheck inference.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat

from ml.final_five_challenger_preview import FrozenChallenger, MAX_BYTES as INPUT_BYTES
from ml.final_five_ranker import LIMITS, _load
from ml.model_history import _canonical, _digest, _synthetic
from ml.settle_snapshot import _iso
from ml.synthetic_session import SessionStore, SessionSaveError, MAX_BYTES

SCHEMA = 'synthetic-final-five-selection-ledger-v1'
MAX_MODELS, MAX_SNAPSHOTS, MAX_RECEIPTS = 5, 20, 100
DISCLAIMERS = {'clock_source': 'local_unverified', 'product_acceptance': False,
               'evaluation_eligible': False, 'training_attempts_tracked': False,
               'hold_status': 'not_checked_in_standalone_ledger',
               'selection_scope': 'retrospective_synthetic_receipt', **LIMITS}


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('selection_request_id_invalid')


def _reason(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 500 or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('selection_reason_invalid')


def _challenger(artifact):
    challenger = FrozenChallenger()
    challenger.artifact = deepcopy(artifact)
    challenger.model = _load(challenger.artifact)
    return challenger


def _comparison(challenger, snapshot):
    value = challenger.view(snapshot, snapshot['snapshot_sha256'][:32])
    if value['status'] != 'ready':
        raise ValueError(value['blocked_reason'])
    return value


def validate_payload(payload):
    if (not isinstance(payload, dict) or
            set(payload) != {'schema_version', 'limits', 'models', 'snapshots', 'receipts'} or
            payload['schema_version'] != SCHEMA or
            _canonical(payload['limits']) != _canonical(DISCLAIMERS)):
        raise ValueError('selection_ledger_schema_invalid')
    models, snapshots, receipts = (payload[k] for k in ('models', 'snapshots', 'receipts'))
    if (not isinstance(models, dict) or not isinstance(snapshots, dict) or
            not isinstance(receipts, list) or len(models) > MAX_MODELS or
            len(snapshots) > MAX_SNAPSHOTS or len(receipts) > MAX_RECEIPTS):
        raise ValueError('selection_ledger_limit')
    loaded = {}
    for key, artifact in models.items():
        loaded[key] = _challenger(artifact)
        if key != artifact['sha256']:
            raise ValueError('selection_model_key_mismatch')
    seen, used_models, used_snapshots = set(), set(), set()
    comparisons = {}
    for index, receipt in enumerate(receipts):
        if (not isinstance(receipt, dict) or set(receipt) != {
                'request_id', 'sequence', 'recorded_at', 'reason', 'model_sha256',
                'snapshot_sha256', 'comparison'} or type(receipt['sequence']) is not int or
                receipt['sequence'] != index + 1):
            raise ValueError('selection_receipt_schema_invalid')
        _identifier(receipt['request_id']); _reason(receipt['reason'])
        _iso(receipt['recorded_at'], 'recorded_at')
        if receipt['request_id'] in seen:
            raise ValueError('selection_request_id_duplicate')
        seen.add(receipt['request_id'])
        model_key, snapshot_key = receipt['model_sha256'], receipt['snapshot_sha256']
        if not isinstance(model_key, str) or not isinstance(snapshot_key, str):
            raise ValueError('selection_reference_invalid')
        if model_key not in models or snapshot_key not in snapshots:
            raise ValueError('selection_reference_missing')
        snapshot = snapshots[snapshot_key]
        if not isinstance(snapshot, dict) or snapshot.get('snapshot_sha256') != snapshot_key:
            raise ValueError('selection_snapshot_key_mismatch')
        pair = model_key, snapshot_key
        if pair not in comparisons:
            comparisons[pair] = _comparison(loaded[model_key], snapshot)
        if _canonical(receipt['comparison']) != _canonical(comparisons[pair]):
            raise ValueError('selection_recomputed_comparison_mismatch')
        used_models.add(model_key); used_snapshots.add(snapshot_key)
    if used_models != set(models) or used_snapshots != set(snapshots):
        raise ValueError('selection_unreferenced_source')
    if len(_canonical({'payload': payload, 'sha256': _digest(payload)}).encode()) + 1 > MAX_BYTES:
        raise ValueError('selection_ledger_too_large')


class SelectionStore(SessionStore):
    filename = 'final-five-selections.json'
    lock_filename = 'final-five-selections.lock'
    temporary_prefix = 'final-five-selections-'
    validate = staticmethod(validate_payload)


class SelectionLedger:
    def __init__(self, state_dir, *, synthetic=False):
        _synthetic(synthetic)
        directory = Path(state_dir)
        if directory.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('session_directory_must_be_outside_repository')
        self.store = SelectionStore(directory)
        self.payload = deepcopy(self.store.loaded) if self.store.loaded is not None else {
            'schema_version': SCHEMA, 'limits': dict(DISCLAIMERS),
            'models': {}, 'snapshots': {}, 'receipts': []}

    def close(self):
        self.store.close()

    def _current(self):
        if self.store.failed:
            raise SessionSaveError('session_restart_required')
        try:
            if self.store._read() != self.store.expected:
                raise ValueError('selection_ledger_changed_outside_process')
        except (ValueError, OSError) as exc:
            self.store.failed = True
            raise SessionSaveError('selection_ledger_changed_restart_required') from exc

    def record(self, artifact, snapshot, request_id, reason):
        self._current()
        _identifier(request_id); _reason(reason)
        challenger = _challenger(artifact)
        comparison = _comparison(challenger, snapshot)
        model_key, snapshot_key = artifact['sha256'], snapshot['snapshot_sha256']
        old = next((r for r in self.payload['receipts'] if r['request_id'] == request_id), None)
        if old is not None:
            if (old['model_sha256'], old['snapshot_sha256'], old['reason']) != (model_key, snapshot_key, reason):
                raise ValueError('selection_request_id_conflict')
            return self.receipt(request_id)
        value = deepcopy(self.payload)
        value['models'][model_key] = deepcopy(artifact)
        value['snapshots'][snapshot_key] = deepcopy(snapshot)
        value['receipts'].append({'request_id': request_id, 'sequence': len(value['receipts']) + 1,
                                 'recorded_at': datetime.now(timezone.utc).isoformat(), 'reason': reason,
                                 'model_sha256': model_key, 'snapshot_sha256': snapshot_key,
                                 'comparison': comparison})
        # Durable checkpoint first. On any uncertain write, memory stays at the
        # previous checkpoint and this process refuses further reads/writes.
        self.store.save(value)
        self.payload = value
        return self.receipt(request_id)

    def receipt(self, request_id):
        self._current(); _identifier(request_id)
        row = next((r for r in self.payload['receipts'] if r['request_id'] == request_id), None)
        if row is None:
            raise ValueError('selection_receipt_not_found')
        return deepcopy({'schema_version': 'synthetic-final-five-selection-receipt-v1',
                         **DISCLAIMERS, 'receipt': row})

    def inspect(self):
        self._current()
        rows = []
        by_race = {}
        for receipt in self.payload['receipts']:
            snapshot = self.payload['snapshots'][receipt['snapshot_sha256']]
            previous = by_race.setdefault(snapshot['race_id'], [])
            rows.append({k: receipt[k] for k in ('request_id', 'sequence', 'recorded_at', 'reason',
                                                'model_sha256', 'snapshot_sha256')})
            rows[-1].update(race_id=snapshot['race_id'], previous_same_race=len(previous),
                            previous_same_pair=sum(r['model_sha256'] == receipt['model_sha256'] and
                                r['snapshot_sha256'] == receipt['snapshot_sha256'] for r in previous),
                            different_model_seen=any(r['model_sha256'] != receipt['model_sha256'] for r in previous))
            previous.append(receipt)
        return {'schema_version': SCHEMA, **DISCLAIMERS, 'revision': _digest(self.payload),
                'model_count': len(self.payload['models']), 'snapshot_count': len(self.payload['snapshots']),
                'receipt_count': len(rows), 'receipts': rows,
                'checkpoint_saved': self.store.expected is not None}


def _read_snapshot(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > INPUT_BYTES:
            raise ValueError('selection_snapshot_file_invalid')
        raw = handle.read(INPUT_BYTES + 1)
        if len(raw) > INPUT_BYTES:
            raise ValueError('selection_snapshot_file_too_large')
    return json.loads(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    record = commands.add_parser('record')
    record.add_argument('experiment', type=Path); record.add_argument('snapshot', type=Path)
    record.add_argument('--request-id', required=True); record.add_argument('--reason', required=True)
    inspect = commands.add_parser('inspect')
    show = commands.add_parser('show'); show.add_argument('request_id')
    for command in (record, inspect, show):
        command.add_argument('--state-dir', type=Path, required=True)
        command.add_argument('--synthetic', action='store_true', required=True)
    args = parser.parse_args(argv)
    ledger = None
    try:
        if args.command == 'record':
            _identifier(args.request_id); _reason(args.reason)
            challenger = FrozenChallenger(args.experiment)
            snapshot = _read_snapshot(args.snapshot)
            _comparison(challenger, snapshot)  # Refuse inputs before creating state/lock.
        ledger = SelectionLedger(args.state_dir, synthetic=args.synthetic)
        if args.command == 'record':
            value = ledger.record(challenger.artifact, snapshot, args.request_id, args.reason)
        else:
            value = ledger.inspect() if args.command == 'inspect' else ledger.receipt(args.request_id)
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, SessionSaveError) as exc:
        parser.exit(1, f'{exc}\n')
    finally:
        if ledger is not None:
            ledger.close()


if __name__ == '__main__':
    raise SystemExit(main())

"""Bounded local synthetic experiment registration, execution and retry audit.

No automatic retry, promotion, global history, or proof of independent testing.
Registration and running checkpoints precede any fit. Uncertain writes stop all
operations until restart; a running record then requires explicit abandonment.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading

from ml.final_five_ranker import LIMITS, experiment_plan, replay_experiment, run_experiment
from ml.final_five_selection_ledger import _read_snapshot
from ml.model_history import _canonical, _digest, _synthetic
from ml.settle_snapshot import _iso
from ml.synthetic_session import MAX_BYTES, SessionSaveError, SessionStore

SCHEMA = 'synthetic-final-five-experiment-ledger-v1'
MAX_INPUTS, MAX_ATTEMPTS, MAX_RECORDS = 5, 20, 200
INPUT_BYTES = 8 * 1024 * 1024
TERMINAL = {'completed', 'blocked', 'failed', 'interrupted'}
LIMITATIONS = {**LIMITS, 'clock_source': 'local_unverified', 'product_acceptance': False,
              'evaluation_eligible': False, 'independent_evaluation_established': False,
              'tracking_scope': 'this_local_ledger_only', 'automatic_retry_enabled': False,
              'hold_status': 'provided_histories_only'}


def _id(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('experiment_id_invalid')


def _reason(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 500 or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('experiment_reason_invalid')


def _inputs(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError('experiment_input_limit')
    if len(_canonical(records).encode()) > INPUT_BYTES:
        raise ValueError('experiment_input_too_large')


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_payload(payload):
    if (not isinstance(payload, dict) or
            set(payload) != {'schema_version', 'limits', 'inputs', 'attempts'} or
            payload['schema_version'] != SCHEMA or
            _canonical(payload['limits']) != _canonical(LIMITATIONS)):
        raise ValueError('experiment_ledger_schema_invalid')
    sources, attempts = payload['inputs'], payload['attempts']
    if (not isinstance(sources, dict) or not isinstance(attempts, list) or
            len(sources) > MAX_INPUTS or len(attempts) > MAX_ATTEMPTS):
        raise ValueError('experiment_ledger_limit')
    for key, records in sources.items():
        _inputs(records)
        if key != _digest(records):
            raise ValueError('experiment_input_digest_mismatch')
    seen, used, plans = {}, set(), {}
    for i, row in enumerate(attempts):
        if (not isinstance(row, dict) or set(row) != {
                'attempt_id', 'sequence', 'registered_at', 'reason', 'retry_of',
                'input_sha256', 'plan', 'status', 'started_at', 'finished_at',
                'terminal_reason', 'result'} or type(row['sequence']) is not int or
                row['sequence'] != i + 1):
            raise ValueError('experiment_attempt_schema_invalid')
        _id(row['attempt_id']); _reason(row['reason']); _iso(row['registered_at'], 'registered_at')
        if row['attempt_id'] in seen:
            raise ValueError('experiment_id_duplicate')
        source = row['input_sha256']
        if not isinstance(source, str) or source not in sources or not isinstance(row['plan'], dict):
            raise ValueError('experiment_source_missing')
        cutoff = row['plan'].get('cutoff'); _iso(cutoff, 'cutoff')
        pair = source, cutoff
        if pair not in plans:
            plans[pair] = experiment_plan(sources[source], cutoff, synthetic=True)
        if _canonical(row['plan']) != _canonical(plans[pair]):
            raise ValueError('experiment_plan_mismatch')
        prior = [r for r in seen.values() if r['input_sha256'] == source and r['plan'] == row['plan']]
        if row['retry_of'] is not None:
            _id(row['retry_of'])
            if (not prior or prior[-1]['attempt_id'] != row['retry_of'] or
                    prior[-1]['status'] not in TERMINAL):
                raise ValueError('experiment_retry_reference_invalid')
        elif prior:
            raise ValueError('experiment_retry_reference_required')
        status = row['status']
        if not isinstance(status, str) or status not in TERMINAL | {'registered', 'running'}:
            raise ValueError('experiment_status_invalid')
        if row['started_at'] is not None:
            _iso(row['started_at'], 'started_at')
        if row['finished_at'] is not None:
            _iso(row['finished_at'], 'finished_at')
        # Local wall-clock values are descriptive, not a monotonic time proof.
        if status == 'registered':
            if any(row[k] is not None for k in ('started_at', 'finished_at', 'terminal_reason', 'result')):
                raise ValueError('experiment_registered_state_invalid')
        elif status == 'running':
            if row['started_at'] is None or any(row[k] is not None for k in ('finished_at', 'terminal_reason', 'result')):
                raise ValueError('experiment_running_state_invalid')
        else:
            if row['finished_at'] is None or (status != 'interrupted' and row['started_at'] is None):
                raise ValueError('experiment_terminal_time_missing')
            if status in {'completed', 'blocked'}:
                result = row['result']
                if (row['terminal_reason'] is not None or not isinstance(result, dict) or
                        set(result) != {'model', 'report'} or
                        (result['model'] is None) != (status == 'blocked')):
                    raise ValueError('experiment_result_invalid')
                replayed = replay_experiment(sources[source], cutoff, result['model'], synthetic=True)
                if _canonical(replayed) != _canonical(result):
                    raise ValueError('experiment_result_mismatch')
            else:
                _reason(row['terminal_reason'])
                if row['result'] is not None:
                    raise ValueError('experiment_failure_has_result')
                if status == 'failed' and row['terminal_reason'] != 'execution_exception':
                    raise ValueError('experiment_failure_code_invalid')
        if status in {'registered', 'running'} and i != len(attempts) - 1:
            raise ValueError('experiment_unfinished_before_later_attempt')
        seen[row['attempt_id']] = row; used.add(source)
    if used != set(sources):
        raise ValueError('experiment_unreferenced_input')
    if len(_canonical({'payload': payload, 'sha256': _digest(payload)}).encode()) + 1 > MAX_BYTES:
        raise ValueError('experiment_ledger_too_large')


class ExperimentStore(SessionStore):
    filename = 'final-five-experiments.json'
    lock_filename = 'final-five-experiments.lock'
    temporary_prefix = 'final-five-experiments-'
    validate = staticmethod(validate_payload)


class ExperimentLedger:
    def __init__(self, state_dir, *, synthetic=False):
        _synthetic(synthetic)
        directory = Path(state_dir)
        if directory.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('session_directory_must_be_outside_repository')
        self.lock = threading.RLock()
        self.store = ExperimentStore(directory)
        self.payload = deepcopy(self.store.loaded) if self.store.loaded is not None else {
            'schema_version': SCHEMA, 'limits': dict(LIMITATIONS), 'inputs': {}, 'attempts': []}

    def close(self):
        with self.lock:
            self.store.close()

    def _current(self):
        if self.store.failed or self.store.directory_fd is None:
            raise SessionSaveError('session_restart_required')
        try:
            if self.store._read() != self.store.expected:
                raise ValueError('experiment_ledger_changed_outside_process')
        except (ValueError, OSError) as exc:
            self.store.failed = True
            raise SessionSaveError('experiment_ledger_changed_restart_required') from exc

    def _row(self, attempt_id):
        _id(attempt_id)
        row = next((r for r in self.payload['attempts'] if r['attempt_id'] == attempt_id), None)
        if row is None:
            raise ValueError('experiment_not_found')
        return row

    def _save(self, payload):
        self.store.save(payload)
        self.payload = payload

    def register(self, records, cutoff, attempt_id, reason, *, retry_of=None):
        with self.lock:
            self._current(); _id(attempt_id); _reason(reason); _inputs(records)
            plan = experiment_plan(records, cutoff, synthetic=True)
            source = _digest(records)
            old = next((r for r in self.payload['attempts'] if r['attempt_id'] == attempt_id), None)
            if old is not None:
                if (old['input_sha256'], old['plan'], old['reason'], old['retry_of']) != (source, plan, reason, retry_of):
                    raise ValueError('experiment_id_conflict')
                return self.show(attempt_id)
            if any(r['status'] not in TERMINAL for r in self.payload['attempts']):
                raise ValueError('experiment_unfinished_requires_resolution')
            value = deepcopy(self.payload)
            value['inputs'][source] = deepcopy(records)
            value['attempts'].append({'attempt_id': attempt_id, 'sequence': len(value['attempts']) + 1,
                                      'registered_at': _now(), 'reason': reason, 'retry_of': retry_of,
                                      'input_sha256': source, 'plan': plan, 'status': 'registered',
                                      'started_at': None, 'finished_at': None,
                                      'terminal_reason': None, 'result': None})
            self._save(value)
            return self.show(attempt_id)

    def run(self, attempt_id):
        with self.lock:
            self._current(); row = self._row(attempt_id)
            if row['status'] in TERMINAL:
                return self.show(attempt_id)  # A response retry never fits again.
            if row['status'] == 'running':
                raise ValueError('experiment_running_outcome_unknown_abandon_before_retry')
            value = deepcopy(self.payload); index = row['sequence'] - 1
            value['attempts'][index].update(status='running', started_at=_now())
            self._save(value)  # Must finish before entering any training code.
            try:
                result = run_experiment(deepcopy(self.payload['inputs'][row['input_sha256']]),
                                        row['plan']['cutoff'], synthetic=True)
                # Check the result before attempting its terminal checkpoint.
                replayed = replay_experiment(self.payload['inputs'][row['input_sha256']],
                                             row['plan']['cutoff'], result['model'], synthetic=True)
                if _canonical(result) != _canonical(replayed):
                    raise ValueError('experiment_execution_result_mismatch')
            except Exception:
                self._current()
                failed = deepcopy(self.payload)
                failed['attempts'][index].update(status='failed', finished_at=_now(),
                                                 terminal_reason='execution_exception')
                self._save(failed)
                raise  # Preserve the exception locally, never arbitrary text in the ledger.
            # A save failure must remain unresolved; do not overwrite it as a
            # training failure or automatically retry the expensive operation.
            self._current()
            value = deepcopy(self.payload)
            value['attempts'][index].update(status='blocked' if result['model'] is None else 'completed',
                                            finished_at=_now(), result=deepcopy(result))
            self._save(value)
            return self.show(attempt_id)

    def abandon(self, attempt_id, reason):
        with self.lock:
            self._current(); _reason(reason); row = self._row(attempt_id)
            if row['status'] == 'interrupted' and row['terminal_reason'] == reason:
                return self.show(attempt_id)
            if row['status'] in TERMINAL:
                raise ValueError('experiment_already_terminal')
            value = deepcopy(self.payload)
            value['attempts'][row['sequence'] - 1].update(status='interrupted', finished_at=_now(),
                                                       terminal_reason=reason)
            self._save(value)
            return self.show(attempt_id)

    def show(self, attempt_id):
        with self.lock:
            self._current(); row = self._row(attempt_id)
            result = row['result']
            return deepcopy({'schema_version': SCHEMA, **LIMITATIONS,
                             'attempt': {k: v for k, v in row.items() if k != 'result'},
                             'report': result['report'] if result else None})

    def export(self, attempt_id):
        with self.lock:
            self._current(); row = self._row(attempt_id)
            if row['status'] != 'completed':
                raise ValueError('experiment_completed_model_required')
            return deepcopy(row['result'])

    def inspect(self):
        with self.lock:
            self._current(); rows = []
            previous = []
            for row in self.payload['attempts']:
                train = {r['race_id'] for r in row['plan']['training']}
                test = {r['race_id'] for r in row['plan']['validation']}
                overlap = []
                for old, old_train, old_test in previous:
                    counts = {'validation_reused': len(test & old_test),
                              'validation_previously_training': len(test & old_train),
                              'training_previously_validation': len(train & old_test)}
                    if any(counts.values()):
                        overlap.append({'attempt_id': old['attempt_id'], **counts})
                rows.append({k: row[k] for k in ('attempt_id', 'sequence', 'status', 'retry_of',
                                                 'input_sha256', 'registered_at', 'reason')})
                rows[-1].update(cutoff=row['plan']['cutoff'], plan_sha256=_digest(row['plan']),
                                previous_registered_overlap=overlap,
                                model_sha256=row['result']['model']['sha256']
                                if row['status'] == 'completed' else None)
                previous.append((row, train, test))
            return {'schema_version': SCHEMA, **LIMITATIONS, 'revision': _digest(self.payload),
                    'attempt_count': len(rows), 'attempts': rows,
                    'overlap_basis': 'all_prior_registrations_including_failed_or_unrun',
                    'checkpoint_saved': self.store.expected is not None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register'); register.add_argument('histories', type=Path)
    register.add_argument('--cutoff', required=True); register.add_argument('--attempt-id', required=True)
    register.add_argument('--reason', required=True); register.add_argument('--retry-of')
    run = commands.add_parser('run'); run.add_argument('attempt_id')
    abandon = commands.add_parser('abandon'); abandon.add_argument('attempt_id'); abandon.add_argument('--reason', required=True)
    show = commands.add_parser('show'); show.add_argument('attempt_id')
    inspect = commands.add_parser('inspect')
    export = commands.add_parser('export'); export.add_argument('attempt_id'); export.add_argument('--output', type=Path, required=True)
    for command in (register, run, abandon, show, inspect, export):
        command.add_argument('--state-dir', type=Path, required=True)
        command.add_argument('--synthetic', action='store_true', required=True)
    args = parser.parse_args(argv); ledger = None
    try:
        if args.command == 'register':
            _id(args.attempt_id); _reason(args.reason)
            records = _read_snapshot(args.histories); _inputs(records)
            experiment_plan(records, args.cutoff, synthetic=args.synthetic)
        ledger = ExperimentLedger(args.state_dir, synthetic=args.synthetic)
        if args.command == 'register':
            value = ledger.register(records, args.cutoff, args.attempt_id, args.reason, retry_of=args.retry_of)
        elif args.command == 'abandon':
            value = ledger.abandon(args.attempt_id, args.reason)
        elif args.command == 'export':
            value = ledger.export(args.attempt_id)
            with args.output.open('x', encoding='utf-8') as handle:
                handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            value = {'exported_model_sha256': value['model']['sha256'], **LIMITATIONS}
        else:
            value = ledger.inspect() if args.command == 'inspect' else getattr(ledger, args.command)(args.attempt_id)
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if args.command == 'run' and value['attempt']['status'] != 'completed' else 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, SessionSaveError) as exc:
        parser.exit(1, f'{exc}\n')
    finally:
        if ledger is not None:
            ledger.close()


if __name__ == '__main__':
    raise SystemExit(main())

"""Loopback-only UI for generated synthetic model development, never production."""
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import permutations
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import RLock
from uuid import uuid4

from ml.dataset import build_rows
from ml.model_history import capture_prediction, settle_snapshot, evaluate_histories, _digest
from ml.offline_preview import render_preview
from ml.model_web_response import model_web_response, render_model_web_preview
from ml.synthetic_demo import make_record
from ml.synthetic_session import SCHEMA, MAX_SNAPSHOTS, SessionStore, SessionSaveError
from ml.settle_snapshot import _iso
from ml.held_review_workspace import ReviewWorkspace, ReviewConflict, parse_json_file, MAX_BYTES as REVIEW_MAX_BYTES


class Workbench:
    def __init__(self, state_dir=None):
        self._temporary = TemporaryDirectory(prefix='keirin-synthetic-')
        self.root = Path(self._temporary.name)
        self.ready = False
        self.snapshots = {}
        self.histories = {}
        self.current = None
        self.lock = RLock()
        self.scheduled = datetime.now(timezone.utc) + timedelta(hours=1)
        self.series = 0
        self.store = None
        self.restored = False
        self.held_review = ReviewWorkspace()
        try:
            if state_dir is not None:
                if Path(state_dir).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
                    raise ValueError('session_directory_must_be_outside_repository')
                self.store = SessionStore(Path(state_dir))
                if self.store.loaded is not None:
                    self._apply(self.store.loaded)
                    self.restored = True
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.store is not None:
            self.store.close()
        self._temporary.cleanup()

    def _payload(self, **changes):
        return {'schema_version':SCHEMA, 'synthetic_only':True,
                'scheduled':self.scheduled.isoformat(), 'series':self.series,
                'snapshots':self.snapshots, 'histories':self.histories, 'current':self.current, **changes}

    def _apply(self, payload):
        self.scheduled = _iso(payload['scheduled'], 'session_scheduled')
        self.series = payload['series']
        self.snapshots = payload['snapshots']
        self.histories = payload['histories']
        self.current = payload['current']

    def _commit(self, payload):
        if self.store is not None:
            self.store.save(payload)
        self._apply(payload)
        return self.state()

    def select(self, key):
        if key not in self.snapshots:
            raise ValueError('snapshot_not_found')
        return self._commit(self._payload(current=key))

    def _train(self):
        if self.ready:
            return
        from ml.train_position_models import train
        rows, summary = build_rows([make_record(i, 7 if i % 2 == 0 else 9) for i in range(16)])
        if len(rows) != 128 or summary['eligible_unique_races'] != 16:
            raise ValueError('synthetic_fixture_invalid')
        source = self.root / 'generated.csv'
        with source.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        metrics = train(source, self.root / 'models', min_races=5, validation_fraction=0.25)
        if metrics['status'] != 'trained_offline_validation_only':
            raise ValueError('synthetic_training_incomplete')
        metrics['evidence_scope'] = 'synthetic_test_only'
        (self.root / 'models' / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
        self.ready = True

    def predict(self, count):
        if type(count) is not int or count not in (7, 9):
            raise ValueError('seven_or_nine_required')
        if self.store is not None and self.store.failed:
            raise SessionSaveError('session_restart_required')
        if len(self.snapshots) >= MAX_SNAPSHOTS:
            raise ValueError('session_limit_export_and_restart')
        self._train()
        from ml.predict_position_models import predict_race
        scheduled, series = self.scheduled, self.series
        now = datetime.now(timezone.utc)
        if now >= scheduled:
            scheduled, series = now + timedelta(hours=1), series + 1
        race_data = make_record(16, count)['training_input']
        race_data['race'].update(date=scheduled.astimezone(timezone(timedelta(hours=9))).date().isoformat(),
                                 venue='SYNTHETIC', race_number=series*10+count, scheduled_start_jst=scheduled.isoformat())
        race_data['odds']['trifecta'] = {'1-2-3':25.4, '2-3-4':72.0}
        if count == 9:
            race_data['odds']['trifecta'] = {'-'.join(map(str,c)): [25.4,72.0,200.0,600.0][i % 4]
                for i,c in enumerate(list(permutations(range(1,10),3))[:24])}
        prediction = predict_race(race_data, self.root / 'models')
        snapshot = capture_prediction(prediction, synthetic=True)
        key = uuid4().hex
        return self._commit(self._payload(snapshots={**self.snapshots, key:snapshot}, current=key,
                                         scheduled=scheduled.isoformat(), series=series))

    def settle(self, key, outcome, odds):
        return self._record(key, {'outcome_combo':outcome, 'settlement_odds':odds})

    def hold(self, key, status, withdrawn=None):
        if status not in ('dead_heat', 'withdrawn', 'cancelled'):
            raise ValueError('result_status_invalid')
        fields = {'result_status':status}
        if status == 'withdrawn':
            fields['withdrawn_car_numbers'] = withdrawn
        elif withdrawn is not None:
            raise ValueError('settlement_fields_invalid')
        return self._record(key, fields)

    def _record(self, key, fields):
        if key not in self.snapshots:
            raise ValueError('snapshot_not_found')
        if key in self.histories:
            raise ValueError('snapshot_already_settled')
        snapshot = self.snapshots[key]
        history = settle_snapshot(snapshot, {
            'race_id':snapshot['race_id'], **fields,
            'result_timestamp':(_iso(snapshot['scheduled_start'], 'scheduled_start') + timedelta(minutes=10)).isoformat(),
        }, synthetic=True)
        return self._commit(self._payload(histories={**self.histories, key:history}, current=key))

    def report(self):
        return evaluate_histories(list(self.histories.values()), synthetic=True)

    def state(self):
        current = None
        if self.current:
            snapshot = self.snapshots[self.current]
            p = snapshot['prediction']
            current = {'snapshot_id':self.current, 'settled':self.current in self.histories,
                       'settlement':self.histories.get(self.current, {}).get('settlement'),
                       'race':p['race'], 'input_quality':p['input_quality'],
                       'selected_predictions':p['selected_predictions']}
        return {'synthetic_only':True, 'model_ready':self.ready, 'current':current,
                'storage':{'mode':'local_file' if self.store else 'temporary', 'restored':self.restored,
                           'write_blocked':bool(self.store and self.store.failed)},
                'snapshot_list':[{'snapshot_id':key, 'rider_count':s['prediction']['input_quality']['rider_count'],
                                  'captured_at':s['captured_at'],
                                  'result_status':self.histories[key]['settlement'].get('result_status','normal') if key in self.histories else 'pending'}
                                 for key,s in sorted(self.snapshots.items(),key=lambda item:(item[1]['captured_at'],item[0]))],
                'saved_snapshots':len(self.snapshots), 'saved_histories':len(self.histories), 'report':self.report()}


def make_server(app: Workbench, port: int = 0):
    page = (Path(__file__).parent / 'templates' / 'synthetic_workbench.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', page, re.S).group(1)
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    review_page = (Path(__file__).parent / 'templates' / 'held_review_workbench.html').read_text(encoding='utf-8')
    review_script = re.search(r'<script>(.*?)</script>', review_page, re.S).group(1)
    review_hash = base64.b64encode(hashlib.sha256(review_script.encode()).digest()).decode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, status, payload, content_type='application/json; charset=utf-8', filename=None, page_script_hash=None):
            data = (json.dumps(payload, ensure_ascii=False, allow_nan=False) if content_type.startswith('application/json') else payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-" + (page_script_hash or script_hash) + "'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers(); self.wfile.write(data)

        def allowed(self, post=False):
            authority = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            ok = self.headers.get('Host') == authority and self.headers.get('Sec-Fetch-Site') != 'cross-site'
            ok = ok and (origin is None or origin == 'http://' + authority)
            if post:
                ok = ok and origin == 'http://' + authority and self.headers.get('X-Keirin-Local') == 'synthetic-only'
            if not ok:
                self.send(403, {'error':'local_same_origin_required'})
            return ok

        def do_GET(self):
            if not self.allowed(): return
            with app.lock:
                if self.path == '/':
                    return self.send(200, page, 'text/html; charset=utf-8')
                if self.path == '/api/state':
                    return self.send(200, app.state())
                if self.path == '/held-review':
                    return self.send(200, review_page, 'text/html; charset=utf-8', page_script_hash=review_hash)
                if self.path == '/api/held-review':
                    return self.send(200, app.held_review.state())
                if self.path == '/export/held-review':
                    return self.send(200, app.held_review.bundle(), filename='synthetic-held-review-bundle.json')
                if self.path == '/export/held-review-report':
                    return self.send(200, app.held_review.report, filename='synthetic-held-review-report.json')
                match = re.fullmatch(r'/(api/model-view|web-view)/([0-9a-f]{32})', self.path)
                if match and match[2] in app.snapshots:
                    try:
                        response = model_web_response(app.snapshots[match[2]], match[2])
                        if match[1] == 'api/model-view':
                            return self.send(200, response)
                        html, digest = render_model_web_preview(match[2])
                        return self.send(200, html, 'text/html; charset=utf-8', page_script_hash=digest)
                    except (ValueError, KeyError, TypeError):
                        return self.send(409, {'error':'model_display_contract_invalid'})
                if self.path == '/export/review':
                    return self.send(200, app.report(), filename='synthetic-review.json')
                if self.path == '/export/histories':
                    return self.send(200, list(app.histories.values()), filename='synthetic-histories.json')
                if self.path == '/export/session':
                    payload = app._payload()
                    return self.send(200, {'payload':payload, 'sha256':_digest(payload)}, filename='synthetic-session.json')
                match = re.fullmatch(r'/(preview|snapshot|history)/([0-9a-f]{32})', self.path)
                if match:
                    kind,key = match.groups()
                    source = app.histories if kind == 'history' else app.snapshots
                    if key in source:
                        if kind == 'preview':
                            return self.send(200, render_preview(source[key]['prediction']), 'text/html; charset=utf-8')
                        return self.send(200, source[key], filename=f'synthetic-{kind}-{key}.json')
            self.send(404, {'error':'not_found'})

        def do_POST(self):
            if not self.allowed(post=True): return
            try:
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError('invalid_body_length')
                length = int(self.headers['Content-Length'])
                limit = 2 * REVIEW_MAX_BYTES + 1024 if self.path == '/api/held-review/import' else 8192 if self.path == '/api/held-review/decision' else 4096
                if not 0 < length <= limit or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError('small_json_body_required')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict): raise ValueError('json_object_required')
                with app.lock:
                    if self.path == '/api/held-review/import' and set(payload) == {'json_text', 'revision'}:
                        result = app.held_review.load(parse_json_file(payload['json_text']), payload['revision'])
                    elif self.path == '/api/held-review/decision' and set(payload) == {'source_sha256', 'evidence_json', 'decision', 'revision'}:
                        result = app.held_review.review(payload['source_sha256'], parse_json_file(payload['evidence_json'], 3072), payload['decision'], payload['revision'])
                    elif self.path == '/api/predict' and set(payload) == {'rider_count'}:
                        result = app.predict(payload['rider_count'])
                    elif self.path == '/api/select' and set(payload) == {'snapshot_id'}:
                        result = app.select(payload['snapshot_id'])
                    elif self.path == '/api/settle' and set(payload) == {'snapshot_id','outcome_combo','settlement_odds'}:
                        result = app.settle(payload['snapshot_id'],payload['outcome_combo'],payload['settlement_odds'])
                    elif self.path == '/api/hold' and set(payload) in (
                            {'snapshot_id','result_status'}, {'snapshot_id','result_status','withdrawn_car_numbers'}):
                        if ('withdrawn_car_numbers' in payload) != (payload['result_status'] == 'withdrawn'):
                            raise ValueError('settlement_fields_invalid')
                        result = app.hold(payload['snapshot_id'],payload['result_status'],payload.get('withdrawn_car_numbers'))
                    else:
                        raise ValueError('unsupported_action_or_fields')
                self.send(200, result)
            except ReviewConflict as exc:
                self.send(409, {'error':str(exc), 'state':app.held_review.state()})
            except SessionSaveError as exc:
                self.send(503, {'error':str(exc), 'state':app.state()})
            except (ValueError, TypeError, KeyError) as exc:
                self.send(400, {'error':str(exc)})
            except Exception:
                self.send(500, {'error':'synthetic_operation_failed'})

    # No bind-host option, filesystem serving, external URL or arbitrary file input.
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--state-dir', type=Path, help='Optional local POSIX directory outside the checkout for synthetic records only.')
    args = parser.parse_args()
    app = Workbench(args.state_dir)
    server = None
    try:
        server = make_server(app, args.port)
        print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'synthetic_only':True}), flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        app.close()


if __name__ == '__main__':
    main()

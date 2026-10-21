from copy import deepcopy
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.final_five_challenger_preview import FrozenChallenger, render_challenger_preview, MAX_BYTES
from ml.final_five_ranker import predict_ranker, run_experiment
from ml.synthetic_session import SCHEMA, FILENAME, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_final_five_ranker import fixtures
from test_synthetic_workbench_final_five_review import dated_snapshot, result


def preview_fixture():
    records, cutoff = fixtures()
    # Keep day 6 unseen by the second stage while preserving valid first-stage chronology.
    unseen_date = dated_snapshot(7, 6)['prediction']['race']['date']
    records = [r for r in records if r['snapshot']['prediction']['race']['date'] != unseen_date]
    experiment = run_experiment(records, cutoff, synthetic=True)
    snapshots = {}
    for count in (7, 9):
        for day, size in ((7, 5), (9, 3), (10, 4)):
            snapshots[f'{len(snapshots)+1:032x}'] = dated_snapshot(count, day, size)
    snapshots['7'*32] = records[0]['snapshot']
    snapshots['8'*32] = dated_snapshot(7, 6)
    snapshots['9'*32] = dated_snapshot(9, 11)
    session = {'schema_version': SCHEMA, 'synthetic_only': True, 'legacy': None,
               'scheduled': snapshots['9'*32]['scheduled_start'], 'current': next(iter(snapshots)),
               'snapshots': snapshots, 'histories': {'9'*32: result(snapshots['9'*32], status='withdrawn')}}
    return experiment, session


class ChallengerPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.experiment, cls.session = preview_fixture()

    def prepare(self, root):
        root = Path(root); path = root/'experiment.json'
        path.write_text(json.dumps(self.experiment))
        state = root/'state'; store = SessionStore(state)
        try: store.save(self.session)
        finally: store.close()
        return path, state

    def test_saved_model_matches_cli_for_seven_nine_and_three_four_five_without_mutation(self):
        with TemporaryDirectory() as root:
            path, state = self.prepare(root); before = path.read_bytes(), (state/FILENAME).read_bytes()
            app = Workbench(state, path)
            try:
                original = deepcopy(app._payload())
                with patch('lightgbm.train', side_effect=AssertionError('display must not train')), patch.object(app, '_train', side_effect=AssertionError('first stage must not train')):
                    for key, snapshot in list(self.session['snapshots'].items())[:6]:
                        response = app.challenger_view(key)
                        direct = predict_ranker(self.experiment['model'], snapshot, synthetic=True)
                        self.assertEqual(response['status'], 'ready')
                        self.assertEqual(response['challenger']['selected_count'], response['baseline']['selected_count'])
                        self.assertEqual([p['combo_key'] for p in response['challenger']['picks']], [p['combo_key'] for p in direct['picks']])
                        for got, expected in zip(response['challenger']['picks'], direct['picks']):
                            self.assertEqual(got, {k: expected[k] for k in got})
                        self.assertEqual(response['model']['sha256'], self.experiment['model']['sha256'])
                        encoded = json.dumps(response)
                        for field in ('model_text', 'training_manifest', 'outcome_combo', 'settlement_odds', 'report', 'trifecta_scores'):
                            self.assertNotIn('"'+field+'"', encoded)
                        for field in ('product_acceptance', 'training_on_request', 'billing_enabled', 'real_data_training_enabled', 'db_write_enabled', 'production_prediction_enabled'):
                            self.assertIs(response[field], False)
                self.assertEqual(app._payload(), original); self.assertFalse(app.ready)
                self.assertEqual(before, (path.read_bytes(), (state/FILENAME).read_bytes()))
            finally: app.close()

    def test_missing_model_known_race_early_prediction_and_hold_have_no_ai_picks(self):
        with TemporaryDirectory() as root:
            path, state = self.prepare(root)
            for model in (None, path):
                app = Workbench(state, model)
                try:
                    keys = [('7'*32, 'training_race_cannot_be_tested'), ('8'*32, 'prediction_precedes_cutoff'), ('9'*32, 'held_race_requires_review')]
                    for key, reason in keys:
                        value = app.challenger_view(key)
                        self.assertEqual(value['status'], 'blocked'); self.assertIsNone(value['challenger'])
                        self.assertEqual(value['blocked_reason'], reason if model else 'model_not_configured')
                        self.assertEqual(value['baseline']['selected_count'], 5)
                    self.assertEqual(app.histories, self.session['histories'])
                finally: app.close()

    def test_model_is_pinned_and_results_or_report_cannot_change_picks(self):
        with TemporaryDirectory() as root:
            path, state = self.prepare(root); app = Workbench(state, path)
            key = next(iter(self.session['snapshots']))
            try:
                value = app.challenger_view(key)
                path.write_text('{broken file after startup')
                app.histories[key] = result(app.snapshots[key], 0, odds=999)
                self.assertEqual(app.challenger_view(key), value)
                app.histories[key] = result(app.snapshots[key], 8, odds=20)
                self.assertEqual(app.challenger_view(key), value)
            finally: app.close()
            with self.assertRaises(ValueError): Workbench(state, path)
            # Failure happens before acquiring state locks; no stale model fallback.
            app = Workbench(state)
            try: self.assertIsNone(app.challenger_view(key)['challenger'])
            finally: app.close()
            payload = deepcopy(self.experiment); payload['report'] = {'untrusted': 'must never be rendered'}
            path.write_text(json.dumps(payload)); app = Workbench(state, path)
            try: self.assertEqual(app.challenger_view(key)['challenger'], value['challenger'])
            finally: app.close()

    def test_invalid_missing_and_nonregular_model_files_refuse_start_without_state(self):
        with TemporaryDirectory() as root:
            path = Path(root)/'model.json'; state = Path(root)/'state'
            with self.assertRaises(OSError): Workbench(state, path)
            for raw in ('{}', '{bad', json.dumps({'model':None,'report':{}}), json.dumps({**self.experiment, 'model':{**self.experiment['model'],'sha256':'0'*64}})):
                path.write_text(raw)
                with self.assertRaises(ValueError): Workbench(state, path)
                self.assertFalse(state.exists())
            with path.open('wb') as handle: handle.truncate(MAX_BYTES+1)
            with self.assertRaises(ValueError): FrozenChallenger(path)
            path.write_text(json.dumps(self.experiment))
            link=Path(root)/'link'; link.symlink_to(path)
            with self.assertRaises(OSError): FrozenChallenger(link)
            hard=Path(root)/'hard'; os.link(path, hard)
            with self.assertRaises(ValueError): FrozenChallenger(path)
            hard.unlink(); fifo=Path(root)/'fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): FrozenChallenger(fifo)
            self.assertFalse(state.exists())

    def test_http_readonly_boundaries_error_clearing_contract_and_restart(self):
        with TemporaryDirectory() as root:
            path, state=self.prepare(root); original=(state/FILENAME).read_bytes(); app=Workbench(state,path)
            server=make_server(app); thread=Thread(target=server.serve_forever,daemon=True); thread.start()
            key=next(iter(self.session['snapshots'])); endpoint='/api/final-five-challenger/'+key
            def get(url, headers=None):
                conn=http.client.HTTPConnection(*server.server_address)
                try:
                    conn.request('GET',url,headers=headers or {}); response=conn.getresponse()
                    return response.status,dict(response.getheaders()),response.read()
                finally: conn.close()
            try:
                with patch('lightgbm.train',side_effect=AssertionError('read only')):
                    code,headers,body=get(endpoint); value=json.loads(body)
                    self.assertEqual(code,200);self.assertEqual(headers['Cache-Control'],'no-store')
                    code,headers,html=get('/final-five-challenger/'+key)
                    self.assertEqual(code,200)
                    script=re.search(r'<script>(.*?)</script>',html.decode(),re.S).group(1)
                    digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                    self.assertIn('sha256-'+digest,headers['Content-Security-Policy'])
                    self.assertIn('/final-five-challenger/',get('/')[2].decode())
                    for headers in ({'Origin':'https://example.invalid'},{'Host':'example.invalid'},{'Sec-Fetch-Site':'cross-site'}):
                        self.assertEqual(get(endpoint,headers)[0],403)
                    for url in (endpoint+'?model=/tmp/file','/api/final-five-challenger/'+'e'*32,'/api/final-five-challenger/../../file'):
                        self.assertEqual(get(url)[0],404)
                    app.store.failed=True
                    self.assertTrue(json.loads(get(endpoint)[2])['storage']['write_blocked'])
                    app.snapshots[key]['snapshot_sha256']='0'*64
                    code,_,body=get(endpoint);self.assertEqual(code,409);self.assertNotIn('picks',json.loads(body))
                    self.assertEqual((state/FILENAME).read_bytes(),original)
            finally: server.shutdown();server.server_close();thread.join();app.close()
            restored=Workbench(state,path)
            try: self.assertEqual(restored.challenger_view(key),value)
            finally: restored.close()

    def test_renderer_validates_identity_and_hashes_the_actual_script(self):
        key='a'*32; html,digest=render_challenger_preview(key)
        script=re.search(r'<script>(.*?)</script>',html,re.S).group(1)
        self.assertEqual(digest,base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())
        for value in ('</script>',None,'a'*31):
            with self.assertRaises(ValueError): render_challenger_preview(value)


if __name__=='__main__':unittest.main()

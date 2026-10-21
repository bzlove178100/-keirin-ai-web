from copy import deepcopy
import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.final_five_selection_ledger import SelectionLedger
from ml.synthetic_session import SessionStore, FILENAME, SessionSaveError
from ml.synthetic_workbench import Workbench, make_server
from test_synthetic_workbench_challenger import preview_fixture


class WorkbenchSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.experiment, cls.session = preview_fixture()

    def prepare(self, root, *, configured=True):
        root = Path(root); model = root/'experiment.json'; state = root/'state'; ledger = root/'selections'
        model.write_text(json.dumps(self.experiment)); store = SessionStore(state)
        try: store.save(self.session)
        finally: store.close()
        return Workbench(state, model, ledger if configured else None), model, state, ledger

    def payload(self, key='00000000000000000000000000000001', request_id='a'*32):
        return {'snapshot_id':key, 'snapshot_sha256':self.session['snapshots'][key]['snapshot_sha256'],
                'model_sha256':self.experiment['model']['sha256'], 'request_id':request_id, 'reason':'画面の合成比較'}

    def save(self, app, payload):
        return app.record_challenger(payload['snapshot_id'], payload['snapshot_sha256'],
                                    payload['model_sha256'], payload['request_id'], payload['reason'])

    def test_explicit_saves_and_restart_preserve_sources_and_never_train(self):
        with TemporaryDirectory() as root:
            app, model, state, ledger = self.prepare(root); original = (state/FILENAME).read_bytes(), model.read_bytes()
            receipts = []
            try:
                with patch('lightgbm.train', side_effect=AssertionError('never train')):
                    for i in range(1,7):
                        key = f'{i:032x}'; request = self.payload(key, str(i)*32)
                        view = app.challenger_view(key)
                        self.assertEqual(view['selection_storage'], {'configured':True,'write_blocked':False})
                        receipts.append(self.save(app, request))
                        self.assertEqual(self.save(app, request), receipts[-1])
                        self.assertEqual(receipts[-1]['receipt']['comparison']['challenger'], view['challenger'])
                    self.assertEqual(app.selection_ledger.inspect()['receipt_count'], 6)
                    self.assertFalse(app.ready)
            finally: app.close()
            self.assertEqual(original, ((state/FILENAME).read_bytes(), model.read_bytes()))
            # Historical receipts remain readable without the current model or prediction session.
            restored = Workbench(final_five_selection_dir=ledger)
            try:
                with patch('lightgbm.train', side_effect=AssertionError('never train')):
                    for i, receipt in enumerate(receipts): self.assertEqual(restored.selection_receipt(str(i+1)*32), receipt)
            finally: restored.close()

    def test_readonly_views_and_disabled_or_invalid_saves_do_not_create_receipts(self):
        with TemporaryDirectory() as root:
            app, _, _, ledger = self.prepare(root, configured=False)
            try:
                self.assertFalse(app.challenger_view('00000000000000000000000000000001')['selection_storage']['configured'])
                with self.assertRaisesRegex(ValueError, 'not_configured'): self.save(app, self.payload())
                self.assertFalse(ledger.exists())
            finally: app.close()
        with TemporaryDirectory() as root:
            app, _, _, _ = self.prepare(root)
            try:
                for _ in range(3): app.challenger_view('00000000000000000000000000000001')
                self.assertIsNone(app.selection_ledger.store.expected)
                for key in ('7','8','9'):
                    with self.assertRaises(ValueError): self.save(app, self.payload(key*32))
                for field, value in (('snapshot_sha256','0'*64),('model_sha256','0'*64),('request_id','invalid'),('reason','')):
                    request = self.payload(); request[field] = value
                    with self.assertRaises(ValueError): self.save(app, request)
                self.assertEqual(app.selection_ledger.inspect()['receipt_count'], 0)
            finally: app.close()

    def test_late_hold_blocks_new_save_but_does_not_rewrite_old_receipt(self):
        with TemporaryDirectory() as root:
            app, _, _, _ = self.prepare(root); request = self.payload()
            try:
                receipt = self.save(app, request); snapshot = deepcopy(app.snapshots[request['snapshot_id']])
                self.assertEqual(app.challenger_view(request['snapshot_id'])['status'], 'ready')
                app.hold(request['snapshot_id'], 'withdrawn', [1])
                request['request_id'] = 'b'*32
                with self.assertRaisesRegex(ValueError, 'held_race_requires_review'): self.save(app, request)
                self.assertEqual(app.selection_receipt('a'*32), receipt)
                self.assertEqual(app.snapshots[request['snapshot_id']], snapshot)
                self.assertEqual(app.selection_ledger.inspect()['receipt_count'], 1)
            finally: app.close()

    def test_changed_prediction_session_or_failed_ledger_blocks_saving(self):
        with TemporaryDirectory() as root:
            app, _, state, _ = self.prepare(root)
            try:
                (state/FILENAME).write_text('external change')
                with self.assertRaisesRegex(SessionSaveError, 'prediction_session_changed'): self.save(app, self.payload())
                self.assertEqual(app.selection_ledger.inspect()['receipt_count'], 0)
                self.assertTrue(app.challenger_view(self.payload()['snapshot_id'])['storage']['write_blocked'])
                self.assertEqual((state/FILENAME).read_text(), 'external change')
            finally: app.close()
        with TemporaryDirectory() as root:
            app, _, _, _ = self.prepare(root)
            try:
                with patch('ml.synthetic_session.os.replace', side_effect=OSError('synthetic disk failure')):
                    with self.assertRaisesRegex(SessionSaveError, 'save_failed'): self.save(app, self.payload())
                self.assertTrue(app.challenger_view(self.payload()['snapshot_id'])['selection_storage']['write_blocked'])
                with self.assertRaisesRegex(SessionSaveError, 'restart_required'): app.selection_receipt('a'*32)
            finally: app.close()

    def test_http_origin_exact_fields_lookup_and_failure_contracts(self):
        with TemporaryDirectory() as root:
            app, _, state, _ = self.prepare(root); original = (state/FILENAME).read_bytes()
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            authority = f'127.0.0.1:{server.server_port}'
            def call(method, url, body=None, headers=None):
                conn = http.client.HTTPConnection(*server.server_address)
                default = {'Origin':'http://'+authority,'X-Keirin-Local':'synthetic-only','Content-Type':'application/json'}
                try:
                    conn.request(method, url, json.dumps(body) if body is not None else None, default if headers is None else headers)
                    response = conn.getresponse()
                    return response.status, dict(response.getheaders()), json.loads(response.read())
                finally: conn.close()
            try:
                request = self.payload(); endpoint = '/api/final-five-selection'
                code, _, _ = call('POST', endpoint, request, {'Content-Type':'application/json'})
                self.assertEqual(code,403)
                for body in ({**request,'extra':True},{**request,'model_sha256':'0'*64}):
                    self.assertEqual(call('POST',endpoint,body)[0],400)
                code, headers, receipt = call('POST',endpoint,request)
                self.assertEqual(code,200); self.assertEqual(headers['Cache-Control'],'no-store')
                self.assertEqual(call('POST',endpoint,request)[2],receipt)
                self.assertEqual(call('POST',endpoint,{**request,'reason':'changed'})[0],400)
                self.assertEqual(call('GET',endpoint+'/'+'a'*32)[2],receipt)
                self.assertEqual(call('GET',endpoint+'/'+'b'*32)[0],404)
                self.assertEqual(call('GET',endpoint+'/'+'a'*32+'?model=other')[0],404)
                encoded = json.dumps(receipt)
                for key in ('model_text','training_manifest','trifecta_scores','outcome_combo'):
                    self.assertNotIn('"'+key+'"',encoded)
                with patch('ml.synthetic_session.os.fsync', side_effect=OSError('synthetic disk failure')):
                    self.assertEqual(call('POST',endpoint,{**request,'request_id':'b'*32})[0],503)
                self.assertEqual(call('GET',endpoint+'/'+'a'*32)[0],503)
                self.assertEqual((state/FILENAME).read_bytes(),original)
            finally: server.shutdown();server.server_close();thread.join();app.close()

    def test_bad_ledger_startup_releases_other_locks_and_preserves_original(self):
        with TemporaryDirectory() as root:
            app, model, state, ledger = self.prepare(root)
            self.save(app,self.payload()); filename = ledger/app.selection_ledger.store.filename; app.close()
            filename.write_text('broken ledger')
            with self.assertRaises(ValueError): Workbench(state,model,ledger)
            self.assertEqual(filename.read_text(),'broken ledger')
            # Failure must not strand the already-acquired prediction/review locks.
            app = Workbench(state,model)
            try: self.assertEqual(len(app.snapshots),9)
            finally: app.close()


if __name__ == '__main__':
    unittest.main()

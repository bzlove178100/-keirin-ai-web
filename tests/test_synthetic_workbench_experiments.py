from copy import deepcopy
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.final_five_experiment_ledger import ExperimentLedger, ExperimentStore
from ml.final_five_experiment_preview import FrozenExperimentAudit, render_experiment_preview
from ml.final_five_selection_ledger import SelectionLedger
from ml.model_history import _digest
from ml.synthetic_session import SCHEMA, FILENAME, MAX_BYTES, SessionSaveError, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_final_five_ranker import fixtures
from test_synthetic_workbench_final_five_review import dated_snapshot


def audit_fixture(root):
    root = Path(root); records, cutoff = fixtures()
    ledger = ExperimentLedger(root/'experiments', synthetic=True)
    try:
        for key, parent in (('1', None), ('2', '1'*32)):
            ledger.register(records, cutoff, key*32, '同じ固定条件の合成試験', retry_of=parent)
            ledger.run(key*32)
        model = ledger.export('1'*32)
        ledger.register([], cutoff, '3'*32, '不足ケース'); ledger.run('3'*32)
        ledger.register(records+[None], cutoff, '4'*32, '失敗の合成ケース')
        with patch('lightgbm.train', side_effect=RuntimeError('private failure detail')):
            try: ledger.run('4'*32)
            except RuntimeError: pass
        ledger.register(records, cutoff, '5'*32, '<img src=x onerror=alert(1)>理由', retry_of='2'*32)
        ledger.abandon('5'*32, '未実行のまま中断を記録')
        ledger.register(records, cutoff, '6'*32, '次回のための登録', retry_of='5'*32)
    finally: ledger.close()
    (root/'model.json').write_text(json.dumps(model))
    snapshots = {f'{i+1:032x}': dated_snapshot(count, day, size)
                 for i, (count, day, size) in enumerate((c,d,s) for c in (7,9) for d,s in ((7,5),(9,3),(10,4)))}
    session = {'schema_version': SCHEMA, 'synthetic_only': True, 'legacy': None,
               'scheduled': dated_snapshot(9, 11)['scheduled_start'], 'current': '0'*31+'1',
               'snapshots': snapshots, 'histories': {}}
    store = SessionStore(root/'state')
    try: store.save(session)
    finally: store.close()
    selections = SelectionLedger(root/'selections', synthetic=True)
    try: selections.record(model['model'], snapshots['0'*31+'1'], 'a'*32, '実験履歴参照の合成選定')
    finally: selections.close()
    return root/'experiments'/ExperimentStore.filename, model


class ExperimentAuditPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TemporaryDirectory(); cls.root = Path(cls.source.name)
        cls.path, cls.model = audit_fixture(cls.root)
        cls.raw = cls.path.read_bytes()

    @classmethod
    def tearDownClass(cls): cls.source.cleanup()

    def test_readonly_projection_all_states_duplicate_models_and_source_immutability(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*.json')}
        with patch('lightgbm.train', side_effect=AssertionError('view cannot train')):
            with patch.object(SessionStore, 'save', side_effect=AssertionError('view cannot write')):
                reader = FrozenExperimentAudit(self.path); view = reader.view()
                self.assertEqual([r['status'] for r in view['attempts']], ['completed','completed','blocked','failed','interrupted','registered'])
                self.assertEqual(view['attempts'][0]['strata'], self.model['report']['strata'])
                matches = [r for r in view['attempts'] if r['model_sha256'] == self.model['model']['sha256']]
                self.assertEqual([r['attempt_id'] for r in matches], ['1'*32, '2'*32])
                self.assertEqual(matches[1]['previous_registered_overlap'][0]['validation_reused'], 8)
                for key in ('evaluation_eligible','product_acceptance','training_on_request','real_data_training_enabled','automatic_retry_enabled'):
                    self.assertIs(view[key], False)
                self.assertIs(view['read_only'], True)
                encoded = json.dumps(view)
                for forbidden in ('model_text','training_manifest','outcome_combo','settlement_odds','trifecta_scores','per_race','private failure detail'):
                    self.assertNotIn(forbidden, encoded)
                view['attempts'][0]['reason'] = 'changed copy'
                self.assertNotEqual(reader.view(), view)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*.json')})

    def test_changed_missing_checkpoint_stops_reader_and_running_restore_never_retries(self):
        for change in ('whitespace', 'missing'):
            with TemporaryDirectory() as root:
                path = Path(root)/ExperimentStore.filename; path.write_bytes(self.raw)
                reader = FrozenExperimentAudit(path)
                if change == 'missing': path.unlink()
                else: path.write_bytes(self.raw+b' ')
                with self.assertRaises(SessionSaveError): reader.view()
                path.write_bytes(self.raw)
                with self.assertRaises(SessionSaveError): reader.view()
                self.assertTrue(FrozenExperimentAudit(path).view()['configured'])
        with TemporaryDirectory() as root:
            path = Path(root)/ExperimentStore.filename; path.write_bytes(self.raw)
            ledger = ExperimentLedger(root, synthetic=True)
            try:
                with patch('lightgbm.train', side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt): ledger.run('6'*32)
            finally: ledger.close()
            saved = path.read_bytes()
            with patch('lightgbm.train', side_effect=AssertionError('running audit cannot retry')):
                reader = FrozenExperimentAudit(path)
                self.assertEqual(reader.view()['attempts'][-1]['status'], 'running')
            self.assertEqual(path.read_bytes(), saved)

    def test_unconfigured_empty_and_bad_checkpoint_are_distinct_before_state_creation(self):
        self.assertEqual(FrozenExperimentAudit().view()['attempts'], [])
        self.assertIsNone(FrozenExperimentAudit().view()['revision'])
        self.assertFalse(FrozenExperimentAudit().view()['configured'])
        with TemporaryDirectory() as root:
            root = Path(root); ledger = ExperimentLedger(root/'empty', synthetic=True)
            try: ledger.store.save(ledger.payload)
            finally: ledger.close()
            empty = FrozenExperimentAudit(root/'empty'/ExperimentStore.filename).view()
            self.assertTrue(empty['configured']); self.assertEqual(empty['attempts'], []); self.assertRegex(empty['revision'], '[0-9a-f]{64}')
            bad = root/'bad.json'; state = root/'state'
            for raw in (b'{}', b'{bad', self.raw.replace(b'"read_only"', b'"unused"')[:5]):
                bad.write_bytes(raw)
                with self.assertRaises(ValueError): Workbench(state, final_five_experiment_ledger=bad)
                self.assertFalse(state.exists())
            with self.assertRaises(OSError): Workbench(state, final_five_experiment_ledger=root/'missing')
            self.assertFalse(state.exists())

    def test_unsafe_files_bounds_rehashed_tampering_and_repository_paths_refused(self):
        with TemporaryDirectory() as root:
            root = Path(root); path = root/'audit.json'; path.write_bytes(self.raw)
            link = root/'link'; link.symlink_to(path)
            with self.assertRaises(OSError): FrozenExperimentAudit(link)
            hard = root/'hard'; os.link(path, hard)
            with self.assertRaises(ValueError): FrozenExperimentAudit(path)
            hard.unlink(); fifo = root/'fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): FrozenExperimentAudit(fifo)
            with path.open('wb') as handle: handle.truncate(MAX_BYTES+1)
            with self.assertRaises(ValueError): FrozenExperimentAudit(path)
            envelope = json.loads(self.raw); envelope['payload']['attempts'][0]['result']['report']['product_acceptance'] = True
            envelope['sha256'] = _digest(envelope['payload']); path.write_text(json.dumps(envelope))
            with self.assertRaises(ValueError): FrozenExperimentAudit(path)
            with self.assertRaisesRegex(ValueError, 'outside_repository'): FrozenExperimentAudit(Path.cwd()/'audit.json')

    def test_http_readonly_routes_csp_host_checks_and_source_changes(self):
        with TemporaryDirectory() as root:
            path = Path(root)/'audit.json'; path.write_bytes(self.raw)
            app = Workbench(final_five_experiment_ledger=path)
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            endpoint = '/api/final-five-experiments'
            def request(url, headers=None, method='GET'):
                conn = http.client.HTTPConnection(*server.server_address)
                try:
                    conn.request(method, url, body='{}' if method=='POST' else None, headers=headers or {})
                    response = conn.getresponse(); return response.status, dict(response.getheaders()), response.read()
                finally: conn.close()
            try:
                with patch('lightgbm.train', side_effect=AssertionError('HTTP cannot train')):
                    code, headers, body = request(endpoint); self.assertEqual(code,200)
                    self.assertEqual(len(json.loads(body)['attempts']),6); self.assertEqual(headers['Cache-Control'],'no-store')
                    for url in ('/final-five-experiments','/final-five-experiments/model/'+'a'*64,'/final-five-experiments/attempt/'+'1'*32):
                        code, headers, html = request(url); self.assertEqual(code,200)
                        script = re.search(r'<script>(.*?)</script>',html.decode(),re.S).group(1)
                        digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                        self.assertIn('sha256-'+digest,headers['Content-Security-Policy'])
                    for url in (endpoint+'?file=elsewhere','/final-five-experiments/model/'+'a'*32,'/final-five-experiments/attempt/../file'):
                        self.assertEqual(request(url)[0],404)
                    for headers in ({'Origin':'https://example.invalid'},{'Host':'example.invalid'},{'Sec-Fetch-Site':'cross-site'}):
                        self.assertEqual(request(endpoint,headers)[0],403)
                    origin='http://127.0.0.1:'+str(server.server_port)
                    for url in (endpoint, endpoint+'/run', endpoint+'/register', endpoint+'/abandon'):
                        self.assertEqual(request(url,{'Origin':origin,'X-Keirin-Local':'synthetic-only','Content-Type':'application/json'},'POST')[0],400)
                    self.assertFalse(app.ready); self.assertEqual(app.snapshots,{})
                    self.assertEqual(path.read_bytes(),self.raw)
                    path.write_bytes(self.raw+b' ')
                    code,_,body=request(endpoint); self.assertEqual(code,503); self.assertNotIn('attempts',json.loads(body))
                    self.assertEqual(path.read_bytes(),self.raw+b' ')
            finally: server.shutdown();server.server_close();thread.join();app.close()

    def test_actual_browser_validator_accepts_projection_and_rejects_false_claims(self):
        valid = FrozenExperimentAudit(self.path).view(); bad = []
        for key in ('evaluation_eligible','product_acceptance','training_on_request','automatic_retry_enabled'):
            value=deepcopy(valid);value[key]=True;bad.append(value)
        for key,value in (('sequence',True),('model_sha256','bad'),('status','running'),('retry_of','9'*32)):
            changed=deepcopy(valid);changed['attempts'][0][key]=value;bad.append(changed)
        value=deepcopy(valid);value['attempts'][0]['counts']['test_races']=False;bad.append(value)
        value=deepcopy(valid);value['attempts'][0]['strata'][0]['races']+=1;bad.append(value)
        value=deepcopy(valid);value['attempts'][1]['previous_registered_overlap'][0]['validation_reused']=201;bad.append(value)
        value=deepcopy(valid);value['attempts'][1]['attempt_id']='1'*32;bad.append(value)
        value=deepcopy(valid);value['attempts'][0]['reason']='x'*501;bad.append(value)
        value=deepcopy(valid);value['configured']=False;bad.append(value)
        html,_=render_experiment_preview();script=re.search(r'<script>(.*?)</script>',html,re.S).group(1)
        script=script.replace("$('refresh').onclick=()=>load();load();",'')
        program="const fs=require('node:fs'),vm=require('node:vm');const {script,good,bad}=JSON.parse(fs.readFileSync(0,'utf8'));for(const data of good)vm.runInNewContext(script+';validate(data);',{data});for(const data of bad){let rejected=false;try{vm.runInNewContext(script+';validate(data);',{data});}catch{rejected=true;}if(!rejected)throw Error('unsafe response accepted');}console.log('validator cases passed');"
        result=subprocess.run(['node','-e',program],input=json.dumps({'script':script,'good':[valid,FrozenExperimentAudit().view()],'bad':bad}),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        for mode,key in (('model','</script>'),('attempt','a'*64),('other',None),('all','a'*32)):
            with self.assertRaises(ValueError):render_experiment_preview(mode,key)


if __name__ == '__main__': unittest.main()

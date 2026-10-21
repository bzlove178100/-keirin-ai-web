from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import http.client
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from ml.final_five_experiment_control import ExperimentConflict, render_experiment_control, unconfigured_state
from ml.final_five_experiment_ledger import ExperimentLedger
from ml.final_five_challenger_preview import FrozenChallenger
from ml.model_history import _digest
from ml.synthetic_session import SCHEMA, SessionStore, SessionSaveError
from ml.synthetic_workbench import Workbench, make_server
from test_final_five_ranker import fixtures
from test_synthetic_workbench_final_five_review import dated_snapshot, result


def control_fixture(root):
    root = Path(root); records, _ = fixtures(); records = records[:14]+records[16:]
    snapshots = {f'{i+1:032x}': r['snapshot'] for i,r in enumerate(records)}
    histories = {f'{i+1:032x}': r for i,r in enumerate(records)}
    payload = {'schema_version': SCHEMA, 'synthetic_only': True, 'legacy': None,
               'scheduled': dated_snapshot(9,11)['scheduled_start'], 'current': '0'*31+'1',
               'snapshots': snapshots, 'histories': histories}
    store = SessionStore(root/'state')
    try: store.save(payload)
    finally: store.close()
    return records[14]['snapshot']['captured_at']


class ExperimentControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.root=Path(self.temp.name)
        self.cutoff=control_fixture(self.root)
        self.app=Workbench(self.root/'state',final_five_experiment_dir=self.root/'experiments')
        self.control=self.app.experiment_control
        self.original=(self.root/'state'/'synthetic-session.json').read_bytes()

    def tearDown(self):
        self.app.close();self.temp.cleanup()

    def registration(self, key='1', retry_of=None):
        state=self.control.state()
        return {'attempt_id': key*32,'reason':'合成実験 '+key,'cutoff':self.cutoff,'retry_of':retry_of,
                'source_revision':state['source']['revision'],'revision':state['audit']['revision']}

    def test_explicit_register_single_fit_terminal_retry_export_and_unchanged_sources(self):
        import lightgbm
        with patch('lightgbm.train', wraps=lightgbm.train) as fit:
            req=self.registration();registered=self.control.register(**req)
            self.assertEqual(registered['audit']['attempts'][0]['status'],'registered');fit.assert_not_called()
            self.assertEqual(self.control.register(**req),registered)
            completed=self.control.run('1'*32,registered['audit']['revision'])
            self.assertEqual(completed['audit']['attempts'][0]['status'],'completed')
            self.assertEqual(self.control.run('1'*32,registered['audit']['revision']),completed)
            self.assertEqual(fit.call_count,1)
            self.assertEqual(self.control.state(),completed)
            exported=self.control.ledger.export('1'*32)
            target=self.root/'model.json';target.write_text(json.dumps(exported))
            self.assertEqual(FrozenChallenger(target).artifact,exported['model'])
        self.assertEqual((self.root/'state'/'synthetic-session.json').read_bytes(),self.original)
        self.assertFalse(self.app.ready);self.assertIsNone(self.app.challenger.artifact)
        self.assertFalse((self.root/'selections').exists())
        self.assertEqual(completed['audit']['loading_policy'],'owned_ledger_current_checkpoint')
        self.assertNotIn('model_text',json.dumps(completed));self.assertNotIn('trifecta_scores',json.dumps(completed))

    def test_revision_source_change_and_late_hold_refuse_fit_then_explicit_replacement(self):
        req=self.registration()
        for field in ('revision','source_revision'):
            with self.assertRaises(ExperimentConflict):self.control.register(**{**req,field:'f'*64})
        registered=self.control.register(**req)
        with self.assertRaises(ValueError):self.control.register(**{**req,'reason':'異なる要求'})
        key='0'*31+'1';payload=self.app._payload();payload['histories']=deepcopy(payload['histories'])
        payload['histories'][key]=result(payload['snapshots'][key],status='withdrawn');self.app._commit(payload)
        with patch('lightgbm.train',side_effect=AssertionError('stale source cannot fit')):
            with self.assertRaises(ExperimentConflict):self.control.run('1'*32,registered['audit']['revision'])
        self.control.abandon('1'*32,'保留追加のため条件を更新',registered['audit']['revision'])
        newer=self.control.register(**self.registration('2'))
        self.assertEqual(newer['audit']['attempts'][1]['counts']['held_races'],1)
        self.assertEqual(newer['audit']['attempts'][0]['status'],'interrupted')
        with self.assertRaises(ExperimentConflict):self.control.abandon('2'*32,'古い画面',registered['audit']['revision'])

    def test_failed_and_unknown_running_restore_never_automatically_refit(self):
        state=self.control.register(**self.registration())
        with patch('lightgbm.train',side_effect=RuntimeError('private training error')):
            with self.assertRaises(RuntimeError):self.control.run('1'*32,state['audit']['revision'])
        state=self.control.state();self.assertEqual(state['audit']['attempts'][0]['status'],'failed')
        self.assertNotIn('private training error',json.dumps(state))
        with patch('lightgbm.train',side_effect=AssertionError('terminal retry')):
            self.control.run('1'*32,'f'*64)
        state=self.control.register(**self.registration('2','1'*32))
        with patch('lightgbm.train',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.control.run('2'*32,state['audit']['revision'])
        self.app.close()
        with patch('lightgbm.train',side_effect=AssertionError('restore cannot fit')):
            self.app=Workbench(self.root/'state',final_five_experiment_dir=self.root/'experiments');self.control=self.app.experiment_control
            state=self.control.state();self.assertEqual(state['audit']['attempts'][-1]['status'],'running')
            with self.assertRaisesRegex(ValueError,'outcome_unknown'):self.control.run('2'*32,state['audit']['revision'])
            done=self.control.abandon('2'*32,'中断後の結果未確認',state['audit']['revision'])
            self.assertEqual(self.control.abandon('2'*32,'中断後の結果未確認',state['audit']['revision']),done)
        newer=self.control.register(**self.registration('3','2'*32));self.assertEqual(len(newer['audit']['attempts']),3)

    def test_external_source_and_ledger_changes_stop_operations_and_startup_releases_locks(self):
        state=self.control.register(**self.registration());path=self.root/'state'/'synthetic-session.json'
        path.write_bytes(self.original+b' ')
        with patch('lightgbm.train',side_effect=AssertionError('changed source')):
            with self.assertRaises(SessionSaveError):self.control.run('1'*32,state['audit']['revision'])
        path.write_bytes(self.original)
        with self.assertRaises(SessionSaveError):self.control.state()
        self.app.close()
        ledgerpath=self.root/'experiments'/'final-five-experiments.json';raw=ledgerpath.read_bytes()
        self.app=Workbench(self.root/'state',final_five_experiment_dir=self.root/'experiments');self.control=self.app.experiment_control
        ledgerpath.write_bytes(raw+b' ')
        with self.assertRaises(SessionSaveError):self.control.audit()
        self.app.close();ledgerpath.write_bytes(b'bad')
        with self.assertRaises(ValueError):Workbench(self.root/'state',final_five_experiment_dir=self.root/'experiments')
        probe=SessionStore(self.root/'state');probe.close()
        ledgerpath.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'choose_readonly'):Workbench(final_five_experiment_ledger=ledgerpath,final_five_experiment_dir=self.root/'experiments')

    def test_uncertain_running_checkpoint_never_fits_and_restores_unknown(self):
        state=self.control.register(**self.registration());store=self.control.ledger.store;original=store.save
        def uncertain(payload):
            original(payload);store.failed=True;raise SessionSaveError('uncertain_after_replace')
        with patch.object(store,'save',side_effect=uncertain),patch('lightgbm.train',side_effect=AssertionError('not durable')):
            with self.assertRaises(SessionSaveError):self.control.run('1'*32,state['audit']['revision'])
        with self.assertRaises(SessionSaveError):self.control.state()
        self.app.close()
        with patch('lightgbm.train',side_effect=AssertionError('no retry')):
            self.app=Workbench(self.root/'state',final_five_experiment_dir=self.root/'experiments');self.control=self.app.experiment_control
            self.assertEqual(self.control.state()['audit']['attempts'][0]['status'],'running')

    def http(self):
        server=make_server(self.app);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(url,body=None,headers=None):
            conn=http.client.HTTPConnection(*server.server_address,timeout=20)
            origin='http://127.0.0.1:'+str(server.server_port)
            base={'Origin':origin,'Content-Type':'application/json','X-Keirin-Local':'synthetic-only'} if body is not None else {}
            try:
                conn.request('POST' if body is not None else 'GET',url,body=json.dumps(body) if body is not None else None,headers={**base,**(headers or {})})
                response=conn.getresponse();return response.status,dict(response.getheaders()),response.read()
            finally:conn.close()
        return server,thread,request

    def test_http_guards_bounded_fields_projection_export_and_disabled_default(self):
        server,thread,request=self.http();endpoint='/api/final-five-training'
        try:
            status,headers,body=request('/final-five-training');self.assertEqual(status,200);self.assertIn('sha256-',headers['Content-Security-Policy'])
            for headers in ({'Origin':'https://foreign.invalid'},{'Host':'foreign.invalid'},{'Sec-Fetch-Site':'cross-site'}):self.assertEqual(request(endpoint,headers=headers)[0],403)
            self.assertEqual(request(endpoint+'?file=elsewhere')[0],404)
            req=self.registration()
            self.assertEqual(request(endpoint+'/register',{**req,'histories':[]})[0],400)
            self.assertEqual(request(endpoint+'/register',{**req,'reason':'x'*5000})[0],400)
            self.assertEqual(request(endpoint+'/register',{**req,'source_revision':'f'*64})[0],409)
            code,_,body=request(endpoint+'/register',req);self.assertEqual(code,200)
            state=json.loads(body);self.assertEqual(request(endpoint+'/register',req)[0],200)
            self.assertEqual(request('/export/final-five-experiment/'+'1'*32)[0],409)
            code,_,body=request(endpoint+'/run',{'attempt_id':'1'*32,'revision':state['audit']['revision']});self.assertEqual(code,200)
            self.assertEqual(json.loads(body)['audit']['attempts'][0]['status'],'completed')
            code,headers,body=request('/export/final-five-experiment/'+'1'*32);self.assertEqual(code,200);self.assertIn('attachment',headers['Content-Disposition'])
            self.assertEqual(json.loads(body),self.control.ledger.export('1'*32))
            audit=json.loads(request('/api/final-five-experiments')[2]);self.assertEqual(audit['loading_policy'],'owned_ledger_current_checkpoint')
            self.assertEqual((self.root/'state'/'synthetic-session.json').read_bytes(),self.original)
            control=self.app.experiment_control;self.app.experiment_control=None
            try:
                self.assertEqual(json.loads(request(endpoint)[2]),unconfigured_state());self.assertEqual(request(endpoint+'/run',{'attempt_id':'1'*32,'revision':'a'*64})[0],400)
            finally:self.app.experiment_control=control
        finally:server.shutdown();server.server_close();thread.join()

    def test_concurrent_run_requests_fit_once_and_live_abandon_cannot_cancel(self):
        import lightgbm
        state=self.control.register(**self.registration());server,thread,request=self.http();entered=Event();release=Event();train=lightgbm.train
        def paused(*args,**kwargs):
            entered.set()
            if not release.wait(10):raise RuntimeError('test gate timeout')
            return train(*args,**kwargs)
        try:
            with patch('lightgbm.train',side_effect=paused) as fit,ThreadPoolExecutor(max_workers=3) as pool:
                body={'attempt_id':'1'*32,'revision':state['audit']['revision']}
                first=pool.submit(request,'/api/final-five-training/run',body)
                self.assertTrue(entered.wait(10));second=pool.submit(request,'/api/final-five-training/run',body)
                abandon=pool.submit(request,'/api/final-five-training/abandon',{**body,'reason':'実行中の取消し要求'})
                release.set();self.assertEqual(first.result()[0],200);self.assertEqual(second.result()[0],200)
                self.assertIn(abandon.result()[0],(400,409));self.assertEqual(fit.call_count,1)
            self.assertEqual(self.control.state()['audit']['attempts'][0]['status'],'completed')
        finally:release.set();server.shutdown();server.server_close();thread.join()

    def test_actual_control_validator_rejects_false_claims_and_bad_pending_identity(self):
        state=self.control.register(**self.registration());bad=[]
        for field in ('real_data_training_enabled','automatic_retry_enabled','model_switch_enabled','product_acceptance'):
            v=deepcopy(state);v[field]=True;bad.append(v)
        v=deepcopy(state);v['source']['histories']=True;bad.append(v)
        v=deepcopy(state);v['audit']['attempts'][0]['status']='completed';bad.append(v)
        v=deepcopy(state);v['audit']['loading_policy']='pinned_checkpoint_with_change_refusal';bad.append(v)
        html,_=render_experiment_control();script=re.search(r'<script>(.*?)</script>',html,re.S).group(1)
        script=script[:script.index('try{const raw')]+script[script.index('function checkState'):script.index('function clear')]
        pending=self.registration('2','1'*32)
        bad_pending=[{**pending,'attempt_id':'Z'*32},{**pending,'cutoff':True},
                     {**pending,'source_revision':'x'},{**pending,'file':'outside'}]
        program="const fs=require('node:fs'),vm=require('node:vm');const {script,good,bad,pending,bad_pending}=JSON.parse(fs.readFileSync(0,'utf8'));for(const data of good)vm.runInNewContext(script+';checkState(data);',{data});vm.runInNewContext(script+';checkPending(data);',{data:pending});for(const [fn,items] of [['checkState',bad],['checkPending',bad_pending]])for(const data of items){let failed=false;try{vm.runInNewContext(script+';'+fn+'(data);',{data});}catch{failed=true;}if(!failed)throw Error('false response accepted');}"
        check=subprocess.run(['node','-e',program],input=json.dumps({'script':script,'good':[state,unconfigured_state()],'bad':bad,'pending':pending,'bad_pending':bad_pending}),capture_output=True,text=True,timeout=10)
        self.assertEqual(check.returncode,0,check.stderr)


if __name__=='__main__':unittest.main()

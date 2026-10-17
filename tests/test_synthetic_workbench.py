import http.client
import json
from threading import Thread
import unittest

from ml.model_history import validate_snapshot
from ml.synthetic_workbench import Workbench, make_server


class SyntheticWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=Workbench();cls.server=make_server(cls.app)
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.authority=f'127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.app.close()

    def request(self,path,body=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=30)
        method='GET' if body is None else 'POST'
        defaults={'Origin':'http://'+self.authority,'X-Keirin-Local':'synthetic-only','Content-Type':'application/json'}
        defaults.update(headers or {})
        connection.request(method,path,body=None if body is None else json.dumps(body),headers=defaults)
        response=connection.getresponse();payload=response.read();status=response.status;response_headers=dict(response.getheaders())
        connection.close()
        return status,payload,response_headers

    def test_boundary_only_local_generated_inputs(self):
        status,body,headers=self.request('/')
        self.assertEqual(status,200);self.assertIn('合成データ専用',body.decode())
        self.assertIn("script-src 'sha256-",headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        for headers in ({'Host':'untrusted.invalid'},{'Origin':'https://untrusted.invalid'},
                        {'X-Keirin-Local':''},{'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.request('/api/predict',{'rider_count':7},headers)[0],403)
        self.assertEqual(self.request('/api/predict',{'rider_count':7},{'Content-Length':'99999'})[0],400)
        self.assertEqual(self.request('/api/predict',{'rider_count':7,'race_data':{'source':'real'}})[0],400)
        self.assertEqual(self.request('/api/predict',{'rider_count':True})[0],400)
        for path in ('/../AGENTS.md','/models/first.txt','/export/unknown'):
            self.assertEqual(self.request(path)[0],404)
        self.assertFalse(self.app.ready)

    def test_complete_browser_api_flow_uses_actual_models(self):
        for count in (7,9):
            status,body,_=self.request('/api/predict',{'rider_count':count})
            self.assertEqual(status,200,body)
            state=json.loads(body);current=state['current'];key=current['snapshot_id']
            self.assertEqual(current['input_quality']['rider_count'],count)
            self.assertEqual(len(current['selected_predictions']['categories']),5)
            status,body,headers=self.request('/snapshot/'+key)
            snap=json.loads(body);validate_snapshot(snap,synthetic=True)
            self.assertIn('attachment',headers['Content-Disposition'])
            original=json.dumps(snap,sort_keys=True)
            bad={'snapshot_id':key,'outcome_combo':'1-1-2','settlement_odds':55.5}
            self.assertEqual(self.request('/api/settle',bad)[0],400)
            valid={**bad,'outcome_combo':'1-2-3' if count==7 else '9-8-7'}
            status,body,_=self.request('/api/settle',valid)
            self.assertEqual(status,200,body)
            self.assertTrue(json.loads(body)['current']['settled'])
            self.assertEqual(self.request('/api/settle',valid)[0],400)
            history=json.loads(self.request('/history/'+key)[1])
            self.assertEqual(json.dumps(history['snapshot'],sort_keys=True),original)
            html=self.request('/preview/'+key)[1].decode()
            self.assertIn(f'全{count*(count-1)*(count-2)}通り',html)
        report=json.loads(self.request('/export/review')[1])
        self.assertEqual(report['status'],'completed_synthetic_frozen_review')
        self.assertEqual(report['evaluated_races'],2)
        self.assertFalse(report['promotion_eligible'])
        self.assertEqual(len(report['model_artifacts']),1)
        self.assertEqual(len(json.loads(self.request('/export/histories')[1])),2)

        for count,status in ((7,'dead_heat'),(9,'withdrawn'),(7,'cancelled')):
            state=json.loads(self.request('/api/predict',{'rider_count':count})[1])
            key=state['current']['snapshot_id']
            event={'snapshot_id':key,'result_status':status}
            if status=='withdrawn':
                self.assertEqual(self.request('/api/hold',event)[0],400)
                self.assertEqual(self.request('/api/hold',{**event,'withdrawn_car_numbers':[True]})[0],400)
                event['withdrawn_car_numbers']=[9]
            self.assertEqual(self.request('/api/hold',{**event,'outcome_combo':'1-2-3'})[0],400)
            code,body,_=self.request('/api/hold',event)
            self.assertEqual(code,200,body)
            current=json.loads(body)['current']
            self.assertEqual(current['settlement']['result_status'],status)
            held=json.loads(self.request('/history/'+key)[1])
            self.assertEqual(held['schema_version'],'ml-held-history-v1')
            self.assertNotIn('outcome_combo',held['settlement'])
            self.assertEqual(json.loads(self.request('/api/state')[1])['current'],current)
            self.assertEqual(self.request('/api/settle',{'snapshot_id':key,'outcome_combo':'1-2-3','settlement_odds':55.5})[0],400)
        report=json.loads(self.request('/export/review')[1])
        self.assertEqual((report['evaluated_races'],report['held_races']),(0,2))
        self.assertEqual(report['metrics'],{})
        self.assertEqual(report['excluded'],{'nonstandard_race_requires_review':5})


if __name__=='__main__':unittest.main()

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import http.client
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.model_history import _canonical, _digest, settle_snapshot
from ml.synthetic_session import SCHEMA, FILENAME, MAX_BYTES, SessionSaveError, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import snapshot, settlement


def saved_session():
    seven, nine = snapshot(7), snapshot(9)
    return {'schema_version':SCHEMA, 'synthetic_only':True, 'series':0,
            'scheduled':seven['scheduled_start'], 'current':'a'*32,
            'snapshots':{'a'*32:seven, 'b'*32:nine},
            'histories':{'a'*32:settle_snapshot(seven,settlement(seven),synthetic=True)}}


class SyntheticSessionTests(unittest.TestCase):
    def test_restore_frozen_records_select_and_finish_without_training(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/'state'; initial=saved_session()
            store=SessionStore(directory);store.save(initial);store.close()
            app=Workbench(directory)
            try:
                self.assertFalse(app.ready)
                self.assertTrue(app.state()['storage']['restored'])
                self.assertEqual(app.snapshots,initial['snapshots'])
                with patch.object(app,'_train',side_effect=AssertionError('restored records must not train')):
                    app.select('b'*32)
                    state=app.hold('b'*32,'withdrawn',[9])
                self.assertEqual((state['report']['evaluated_races'],state['report']['held_races']),(1,1))
                self.assertEqual(app.snapshots,initial['snapshots'])
                report=app.report()
            finally:app.close()
            app=Workbench(directory)
            try:
                self.assertEqual(app.current,'b'*32)
                self.assertEqual(app.report(),report)
                self.assertEqual(app.histories['b'*32]['settlement']['withdrawn_car_numbers'],[9])
                with self.assertRaisesRegex(ValueError,'already_settled'):app.settle('a'*32,'1-2-3',50)
            finally:app.close()
            self.assertEqual({p.name for p in directory.iterdir()},{FILENAME,'session.lock','held-review'})
            self.assertEqual((directory/FILENAME).stat().st_mode & 0o777,0o600)

    def test_failed_write_does_not_change_memory_or_previous_file(self):
        for operation in ('os.fsync','os.replace'):
            with self.subTest(operation=operation),TemporaryDirectory() as tmp:
                directory=Path(tmp)/'state';store=SessionStore(directory);store.save(saved_session());store.close()
                original=(directory/FILENAME).read_bytes();app=Workbench(directory)
                try:
                    with patch('ml.synthetic_session.'+operation,side_effect=OSError('synthetic disk failure')):
                        with self.assertRaisesRegex(SessionSaveError,'save_failed'):app.select('b'*32)
                    self.assertEqual(app.current,'a'*32)
                    self.assertEqual((directory/FILENAME).read_bytes(),original)
                    self.assertTrue(app.state()['storage']['write_blocked'])
                    with self.assertRaisesRegex(SessionSaveError,'restart_required'):app.select('b'*32)
                    self.assertEqual(list(directory.glob('*.partial')),[])
                finally:app.close()
                restored=Workbench(directory)
                try:self.assertEqual(restored.current,'a'*32)
                finally:restored.close()

    def test_after_replace_failure_requires_restart_to_reconcile(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/'state';store=SessionStore(directory);store.save(saved_session());store.close()
            app=Workbench(directory);real_fsync=os.fsync;calls=[]
            def fail_directory_sync(fd):
                calls.append(fd)
                if len(calls)==2:raise OSError('synthetic directory sync failure')
                real_fsync(fd)
            try:
                with patch('ml.synthetic_session.os.fsync',side_effect=fail_directory_sync):
                    with self.assertRaisesRegex(SessionSaveError,'save_uncertain'):app.select('b'*32)
                self.assertEqual(app.current,'a'*32)
                self.assertTrue(app.store.failed)
            finally:app.close()
            restored=Workbench(directory)
            try:self.assertEqual(restored.current,'b'*32)
            finally:restored.close()

    def test_http_save_failure_reports_blocked_state_without_claiming_success(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/'state';store=SessionStore(directory);store.save(saved_session());store.close()
            app=Workbench(directory);server=make_server(app)
            thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                authority=f'127.0.0.1:{server.server_port}'
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                with patch('ml.synthetic_session.os.replace',side_effect=OSError('synthetic write failure')):
                    connection.request('POST','/api/select',json.dumps({'snapshot_id':'b'*32}),
                                       {'Origin':'http://'+authority,'X-Keirin-Local':'synthetic-only','Content-Type':'application/json'})
                    response=connection.getresponse();body=json.loads(response.read());connection.close()
                self.assertEqual(response.status,503)
                self.assertTrue(body['state']['storage']['write_blocked'])
                self.assertEqual(body['state']['current']['snapshot_id'],'a'*32)
                self.assertEqual(body['error'],'session_save_failed_restart_required')
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                connection.request('GET','/export/session')
                response=connection.getresponse();backup=json.loads(response.read());connection.close()
                self.assertEqual(response.status,200)
                self.assertEqual(backup['sha256'],_digest(backup['payload']))
                self.assertEqual(set(backup['payload']['snapshots']),{'a'*32,'b'*32})
            finally:server.shutdown();server.server_close();thread.join();app.close()

    def test_concurrent_process_and_external_edits_are_not_overwritten(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/'state';store=SessionStore(directory)
            try:
                store.save(saved_session())
                code='from pathlib import Path;from ml.synthetic_session import SessionStore;SessionStore(Path('+repr(str(directory))+'))'
                result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15)
                self.assertNotEqual(result.returncode,0);self.assertIn('session_already_open',result.stderr)
                (directory/FILENAME).write_bytes(b'broken external edit')
                with self.assertRaisesRegex(SessionSaveError,'save_failed'):store.save(saved_session())
                self.assertEqual((directory/FILENAME).read_bytes(),b'broken external edit')
            finally:store.close()
            with self.assertRaises(ValueError):Workbench(directory)
            self.assertEqual((directory/FILENAME).read_bytes(),b'broken external edit')

    def test_corrupt_unsafe_mismatched_and_oversized_state_fail_closed(self):
        initial=saved_session()
        variants=[]
        for mutate in (lambda p:p.update(synthetic_only=False), lambda p:p.update(current='c'*32),
                       lambda p:p.update(series=True), lambda p:p.update(histories={'c'*32:p['histories']['a'*32]}),
                       lambda p:p['snapshots']['b'*32]['prediction']['model_artifact'].update(evidence_scope='real'),
                       lambda p:p['histories']['a'*32]['snapshot']['prediction']['trifecta_scores'][0].update(odds=999)):
            bad=deepcopy(initial);mutate(bad)
            variants.append(_canonical({'payload':bad,'sha256':_digest(bad)}).encode())
        variants += [b'{',_canonical({'payload':initial,'sha256':'bad'}).encode()]
        for data in variants:
            with self.subTest(size=len(data)),TemporaryDirectory() as tmp:
                directory=Path(tmp);path=directory/FILENAME;path.write_bytes(data)
                with self.assertRaises(ValueError):Workbench(directory)
                self.assertEqual(path.read_bytes(),data)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/FILENAME
            with path.open('wb') as file:file.truncate(MAX_BYTES+1)
            with self.assertRaisesRegex(ValueError,'file_invalid'):SessionStore(Path(tmp))

    def test_links_nonregular_files_and_repository_storage_are_refused(self):
        for kind in ('symlink','fifo'):
            with self.subTest(kind=kind),TemporaryDirectory() as tmp:
                directory=Path(tmp)/'state';directory.mkdir();path=directory/FILENAME
                target=Path(tmp)/'target';target.write_bytes(b'unchanged')
                if kind=='symlink':path.symlink_to(target)
                else:os.mkfifo(path)
                with self.assertRaises((OSError,ValueError)):SessionStore(directory)
                self.assertEqual(target.read_bytes(),b'unchanged')
        with self.assertRaisesRegex(ValueError,'outside_repository'):
            Workbench(Path(__file__).resolve().parents[1]/'synthetic-test-state')

    def test_expired_session_gets_new_race_identity_but_preserves_old_results(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/'state';store=SessionStore(directory);store.save(saved_session());store.close()
            app=Workbench(directory);old=deepcopy(app.snapshots)
            try:
                with patch('ml.synthetic_workbench.datetime',wraps=datetime) as clock:
                    clock.now.return_value=max(datetime.now(timezone.utc),app.scheduled)+timedelta(hours=2)
                    state=app.predict(7)  # Real generated model; restored records are never training input.
                key=state['current']['snapshot_id']
                self.assertEqual(app.series,1)
                self.assertNotEqual(app.snapshots[key]['race_id'],old['a'*32]['race_id'])
                self.assertEqual(app.snapshots['a'*32],old['a'*32])
                app.settle(key,'1-2-3',55.5)
                self.assertEqual(app.report()['evaluated_races'],2)
                # An old unfinished race uses its original schedule, not the new series.
                app.hold('b'*32,'cancelled')
                self.assertEqual(datetime.fromisoformat(app.histories['b'*32]['settlement']['result_timestamp']),
                                 datetime(2026,10,17,2,10,tzinfo=timezone.utc))
            finally:app.close()


if __name__=='__main__':unittest.main()

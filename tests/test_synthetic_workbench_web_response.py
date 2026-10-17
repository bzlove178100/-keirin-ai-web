import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

from ml.model_history import _digest
from ml.model_web_response import model_web_response, render_model_web_preview
from test_model_history import snapshot

ROOT = Path(__file__).resolve().parents[1]
KEY = 'a'*32


class ModelWebResponseTests(unittest.TestCase):
    def test_projection_preserves_frozen_selection_and_excludes_metadata(self):
        outputs = []
        for count in (7, 9):
            snap = snapshot(count)
            snap['prediction']['private_extra'] = {'token':'synthetic-secret-marker'}
            snap['snapshot_sha256'] = _digest({k:v for k,v in snap.items() if k != 'snapshot_sha256'})
            before = deepcopy(snap)
            response = model_web_response(snap, KEY)
            self.assertEqual(snap, before)
            self.assertEqual(response['quality']['rider_count'], count)
            for key, category in response['categories'].items():
                source = snap['prediction']['selected_predictions']['categories'][key]
                self.assertEqual(category['picks'], [{k:p[k] for k in ('rank','combo_key','estimated_probability','odds')} for p in source['picks']])
            serialized = json.dumps(response)
            for excluded in ('synthetic-secret-marker','trifecta_scores','prediction-snapshot-v1','reason','score_contributions'):
                self.assertNotIn(excluded, serialized)
            outputs.append(response)
        result = subprocess.run(['node','tests/test_synthetic_workbench_web_response.cjs'], cwd=ROOT,
                                input=json.dumps(outputs), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('ML display rejection and clearing PASS', result.stdout)

    def test_rejects_invalid_source_and_identity(self):
        snap = snapshot()
        for key in ('../x', 'A'*32, '', None, True):
            with self.assertRaises(ValueError): model_web_response(snap,key)
            with self.assertRaises(ValueError): render_model_web_preview(key)
        bad = deepcopy(snap); bad['prediction']['trifecta_scores'][0]['odds'] = 99
        with self.assertRaises(ValueError): model_web_response(bad,KEY)
        bad = deepcopy(snap); bad['db_write_enabled'] = True
        bad['snapshot_sha256'] = _digest({k:v for k,v in bad.items() if k != 'snapshot_sha256'})
        with self.assertRaises(ValueError): model_web_response(bad,KEY)

    def test_reuses_only_existing_renderers_with_matching_csp(self):
        html, digest = render_model_web_preview(KEY)
        scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
        self.assertEqual(len(scripts),1)
        script = scripts[0]
        self.assertEqual(digest, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())
        source = (ROOT/'index.html').read_text()
        renderer = source[source.index('function appendPick(box, pick) {'):source.index('function renderDryRun(data) {')]
        self.assertIn(renderer, script)
        for excluded in ('function renderDryRun','function runRealDryRun','supabase','prediction-snapshot-v1'):
            self.assertNotIn(excluded, script)
        result = subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__': unittest.main()

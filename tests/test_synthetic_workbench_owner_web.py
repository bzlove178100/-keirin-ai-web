import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ml.model_web_response import model_web_response
from ml.prepare_owner_web_preview import prepare, prepare_html, SCRIPTS
from test_model_history import snapshot

ROOT = Path(__file__).resolve().parents[1]


def bundle():
    return {'schema_version':'keirin-synthetic-model-bundle-v1',
            'views':[model_web_response(snapshot(n),str(n)*32) for n in (7,9)]}


class OwnerWebTests(unittest.TestCase):
    def test_owner_controller_with_real_handler_and_existing_renderer(self):
        result = subprocess.run(['node','tests/test_synthetic_workbench_owner_web.cjs'],cwd=ROOT,
                                input=json.dumps(bundle()),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('owner Web 7/9 and stale-response isolation PASS',result.stdout)

    def test_candidate_is_external_reproducible_and_does_not_overwrite(self):
        original = (ROOT/'index.html').read_bytes()
        with TemporaryDirectory() as tmp:
            output = Path(tmp)/'candidate'
            receipt = prepare(output)
            self.assertFalse(receipt['deployed'])
            self.assertEqual(receipt['source_index_sha256'],hashlib.sha256(original).hexdigest())
            for name,digest in receipt['files'].items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),digest)
            html = (output/'index.html').read_text()
            self.assertEqual(html,prepare_html(original.decode()))
            # Authentication and existing prediction paths are left byte-identical.
            for start,end in [('async function refreshSessionIfNeeded()', 'async function loadProfile()'),
                              ('async function authenticatedGet(', 'function clearCategory('),
                              ('function appendPick(', 'function japanTodayString()')]:
                text = original.decode()
                self.assertIn(text[text.index(start):text.index(end)],html)
            for code in re.findall(r'<script>(.*?)</script>',html,re.S):
                result = subprocess.run(['node','--check'],input=code,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
            with self.assertRaises(FileExistsError):prepare(output)
            with self.assertRaisesRegex(ValueError,'already_prepared'):prepare_html(html)
        self.assertEqual((ROOT/'index.html').read_bytes(),original)
        with self.assertRaisesRegex(ValueError,'outside_repository'):prepare(ROOT/'must-not-create-owner-candidate')
        with self.assertRaisesRegex(ValueError,'anchor_changed'):
            prepare_html(original.decode().replace('async function logout() {','async function logoutChanged() {'))


if __name__ == '__main__': unittest.main()

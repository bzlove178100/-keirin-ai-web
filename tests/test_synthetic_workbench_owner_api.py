import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ml.synthetic_demo import make_record
from ml.synthetic_model_bundle import prepare_bundle

ROOT = Path(__file__).resolve().parents[1]


class OwnerModelApiTests(unittest.TestCase):
    def test_generated_model_bundle_through_actual_owner_handler(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)/'bundle'
            receipt = prepare_bundle(output)
            module = output/'synthetic_model_views.ts'
            self.assertEqual(hashlib.sha256(module.read_bytes()).hexdigest(),receipt['module_sha256'])
            self.assertEqual([s['rider_count'] for s in receipt['snapshots']],[7,9])
            self.assertFalse(receipt['deployed'])
            legacy = make_record(16,7)['training_input']
            for player in legacy['players']:
                player['name'] = 'SYNTHETIC-' + str(player['car_number'])
            result = subprocess.run(['node','tests/test_synthetic_workbench_owner_api.cjs',str(module)],cwd=ROOT,
                                    input=json.dumps({'legacy_input':legacy}),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('legacy dry-run PASS',result.stdout)
            before = module.read_bytes()
            with self.assertRaises(FileExistsError): prepare_bundle(output)
            self.assertEqual(module.read_bytes(),before)

    def test_cli_rejects_missing_synthetic_flag_and_checkout_output(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)/'bundle'
            result = subprocess.run([sys.executable,'-m','ml.synthetic_model_bundle','--output-dir',str(output)],cwd=ROOT,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError,'outside_repository'):
            prepare_bundle(ROOT/'synthetic-bundle-must-not-exist')


if __name__ == '__main__': unittest.main()

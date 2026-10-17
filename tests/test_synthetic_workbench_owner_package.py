import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.owner_review_package import prepare, verify


class PackageTests(unittest.TestCase):
    def test_generated_package_moves_without_training_and_rejects_damage(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp)/'created'
            result = prepare(source, synthetic=True)
            self.assertEqual([s['rider_count'] for s in result['snapshots']], [7, 9])
            self.assertFalse(result['deployed'])
            with self.assertRaises(FileExistsError):
                prepare(source, synthetic=True)
            moved = Path(tmp)/'copied'
            shutil.copytree(source, moved)
            shutil.rmtree(source)
            # A fresh interpreter forbids importing model/training code entirely.
            code = """import builtins,sys,json
original=builtins.__import__
def guard(name,*a,**kw):
 if any(part in name for part in ('lightgbm','synthetic_workbench','synthetic_model_bundle')): raise RuntimeError('unexpected training dependency')
 return original(name,*a,**kw)
builtins.__import__=guard
from ml.owner_review_package import verify
print(json.dumps(verify(sys.argv[1])))
"""
            proc = subprocess.run([sys.executable, '-c', code, str(moved)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), result)
            target = moved/'web/index.html'
            original = target.read_bytes()
            target.write_bytes(original + b'changed')
            with self.assertRaisesRegex(ValueError, 'digest_mismatch'):
                verify(moved)
            target.write_bytes(original)
            extra = moved/'extra.txt'
            extra.write_text('unexpected')
            with self.assertRaisesRegex(ValueError, 'file_set_mismatch'):
                verify(moved)
            extra.unlink()
            target.unlink()
            with self.assertRaisesRegex(ValueError, 'file_set_mismatch'):
                verify(moved)
            target.symlink_to(moved/'web/model-web-response.js')
            with self.assertRaisesRegex(ValueError, 'regular_files_required'):
                verify(moved)
            target.unlink()
            target.write_bytes(original)
            manifest = moved/'package.json'
            bad = json.loads(manifest.read_text())
            receipt_path = moved/'bundle/bundle_receipt.json'
            receipt_original = receipt_path.read_bytes()
            receipt_bad = json.loads(receipt_original)
            receipt_bad['snapshots'][0]['model_artifact_sha256'] = '0' * 64
            receipt_path.write_text(json.dumps(receipt_bad))
            changed = json.loads(manifest.read_text())
            changed['files']['bundle/bundle_receipt.json'] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'snapshot_mismatch'):
                verify(moved)
            receipt_path.write_bytes(receipt_original)
            bad['deployed'] = True
            manifest.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'manifest_invalid'):
                verify(moved)

    def test_failed_export_has_no_completion_receipt(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)/'partial'
            with patch('ml.synthetic_model_bundle.prepare_bundle', side_effect=OSError('synthetic failure')):
                with self.assertRaises(OSError):
                    prepare(output, synthetic=True)
            self.assertFalse((output/'package.json').exists())
            with self.assertRaisesRegex(ValueError, 'file_set_mismatch'):
                verify(output)
            with self.assertRaisesRegex(ValueError, 'synthetic_mode_required'):
                prepare(Path(tmp)/'no-flag')
            self.assertFalse((Path(tmp)/'no-flag').exists())


if __name__ == '__main__': unittest.main()

import hashlib
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ml.prepare_integrated_candidate import prepare


class CandidateTests(unittest.TestCase):
    def test_composition_deletion_and_fail_closed_overlap(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init')
            def commit(message):
                git('add', '.')
                git('-c', 'user.name=Synthetic', '-c', 'user.email=test@example.invalid', 'commit', '-m', message)
                return git('rev-parse', 'HEAD')
            (repo/'keep').write_text('base')
            (repo/'delete').write_text('remove me')
            base = commit('base')
            (repo/'keep').write_text('first')
            first = commit('first')
            git('checkout', '--detach', base)
            (repo/'delete').unlink()
            (repo/'new').write_text('second')
            second = commit('second')
            output = root/'candidate'
            manifest = prepare(repo, base, [first, second], output)
            self.assertEqual((output/'source/keep').read_text(), 'first')
            self.assertEqual((output/'source/new').read_text(), 'second')
            self.assertFalse((output/'source/delete').exists())
            self.assertFalse((output/'source/.git').exists())
            self.assertEqual(manifest['verification'], 'not_run')
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((output/'source'/name).read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                prepare(repo, base, [first, second], output)
            with self.assertRaisesRegex(ValueError, 'outside_repository'):
                prepare(repo, base, [first], repo/'candidate')
            with self.assertRaisesRegex(ValueError, 'full_commit_sha'):
                prepare(repo, base, ['HEAD'], root/'invalid')
            (repo/'keep').write_text('conflict')
            conflict = commit('overlap')
            with self.assertRaisesRegex(ValueError, 'overlapping_component_path:keep'):
                prepare(repo, base, [first, conflict], root/'conflict')
            self.assertFalse((root/'conflict').exists())
            self.assertEqual(git('status', '--porcelain'), '')


if __name__ == '__main__':
    unittest.main()

from hashlib import sha256
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.host_trust import HostTrustError, snapshot_trust


class TrustTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.ca = self.root / "ca.crt"
        self.ca.write_bytes(b"SYNTHETIC:CA")
        self.pin = sha256(self.ca.read_bytes()).hexdigest()

    def tearDown(self):
        self.directory.cleanup()

    def reject(self, path=None, pin=None):
        with self.assertRaisesRegex(HostTrustError, "^host_trust_invalid$") as caught:
            snapshot_trust(str(path or self.ca), pin or self.pin)
        self.assertIsNone(caught.exception.__context__)

    def test_pinned_snapshot_cannot_be_written_or_truncated(self):
        trust = snapshot_trust(str(self.ca), self.pin)
        path = trust.path
        try:
            self.ca.write_bytes(b"SYNTHETIC:replacement")
            self.assertEqual(Path(path).read_bytes(), b"SYNTHETIC:CA")
            fd = os.open(path, os.O_RDWR)
            try:
                with self.assertRaises(OSError):
                    os.write(fd, b"bad")
                with self.assertRaises(OSError):
                    os.ftruncate(fd, 0)
            finally:
                os.close(fd)
        finally:
            trust.close()
        self.assertFalse(Path(path).exists())

    def test_wrong_hash_and_file_replacement(self):
        self.reject(pin="0" * 64)
        replacement = self.root / "new.crt"
        replacement.write_bytes(b"SYNTHETIC:other")
        replacement.replace(self.ca)
        self.reject()

    def test_symlinks_in_file_or_parent_are_rejected(self):
        link = self.root / "link.crt"
        link.symlink_to(self.ca)
        self.reject(link)
        directory_link = self.root / "linked"
        directory_link.symlink_to(self.root, target_is_directory=True)
        self.reject(directory_link / "ca.crt")

    def test_mutable_permissions_and_multiple_links(self):
        self.ca.chmod(0o666)
        self.reject()
        self.ca.chmod(0o644)
        self.root.chmod(0o777)
        self.reject()
        self.root.chmod(0o700)
        os.link(self.ca, self.root / "hardlink.crt")
        self.reject()

    def test_nonregular_empty_and_oversized_files(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        self.reject(fifo)
        for content in (b"", b"x" * 131073):
            self.ca.write_bytes(content)
            self.reject(pin=sha256(content).hexdigest())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Lock
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.durable_secret_store import (  # noqa: E402
    DurableSecretBackendAmbiguousWrite,
    DurableSecretBackendConflict,
)
from tests.support.durable_backend_conformance import run_durable_backend_conformance  # noqa: E402


class FileBackedTestBackend:
    """Test-only persistent backend used to prove the reusable harness itself."""

    def __init__(self, path: Path, lock: Lock, fault: dict[str, object]) -> None:
        self._path = path
        self._lock = lock
        self._fault = fault

    def _load(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict[str, object]]) -> None:
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        os.replace(temp, self._path)

    def read(self, key: str):
        with self._lock:
            value = self._load().get(key)
            return None if value is None else dict(value)

    def compare_and_swap(self, key: str, *, expected_version: int, replacement):
        with self._lock:
            data = self._load()
            current = data.get(key)
            if current is None or current.get("version") != expected_version:
                raise DurableSecretBackendConflict("test_backend_conflict")

            mode = self._fault.pop("mode", None)
            if mode == "ambiguous_before":
                raise DurableSecretBackendAmbiguousWrite("test_backend_ambiguous")

            stored = dict(replacement)
            data[key] = stored
            self._save(data)

            if mode == "ambiguous_after":
                raise DurableSecretBackendAmbiguousWrite("test_backend_ambiguous")
            return dict(stored)


class FileBackedFixture:
    def __init__(self, root: Path) -> None:
        self.path = root / "backend.json"
        self.lock = Lock()
        self.fault: dict[str, object] = {}

    def backend(self):
        return FileBackedTestBackend(self.path, self.lock, self.fault)

    def seed(self, key: str, record):
        with self.lock:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                data = {}
            if key in data:
                raise AssertionError("test_seed_duplicate")
            data[key] = dict(record)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
            os.replace(temp, self.path)

    def reopen(self):
        # New client object, same durable path and synchronization primitive.
        return FileBackedTestBackend(self.path, self.lock, self.fault)

    def arm_ambiguous_write(self, *, commits: bool):
        if self.fault:
            raise AssertionError("fault_already_armed")
        self.fault["mode"] = "ambiguous_after" if commits else "ambiguous_before"


class DurableBackendConformanceHarnessTest(unittest.TestCase):
    def test_file_backed_reference_fixture_passes_backend_contract(self):
        with TemporaryDirectory() as tmp:
            report = run_durable_backend_conformance(FileBackedFixture(Path(tmp)))
        self.assertTrue(report.passed, report.to_safe_dict())
        self.assertTrue(all(report.to_safe_dict().values()))

    def test_report_is_metadata_only(self):
        with TemporaryDirectory() as tmp:
            report = run_durable_backend_conformance(
                FileBackedFixture(Path(tmp)),
                key="synthetic-private-looking-key",
            )
        rendered = json.dumps(report.to_safe_dict(), sort_keys=True)
        self.assertNotIn("synthetic-private-looking-key", rendered)
        self.assertNotIn("concurrent-a", rendered)
        self.assertNotIn("ambiguous-after-commit", rendered)


if __name__ == "__main__":
    unittest.main()

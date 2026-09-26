from __future__ import annotations

import multiprocessing
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.durable_secret_store import DurableSecretBackendConflict  # noqa: E402
from tests.support.durable_backend_conformance import run_durable_backend_conformance  # noqa: E402
from tests.support.sqlite_test_backend import SQLiteTestBackend  # noqa: E402


class SQLiteFixture:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fault: dict[str, str] = {}

    def backend(self):
        return SQLiteTestBackend(self.path, self.fault)

    def seed(self, key, record):
        self.backend().seed(key, record)

    def reopen(self):
        return SQLiteTestBackend(self.path, self.fault)

    def arm_ambiguous_write(self, *, commits):
        self.fault["mode"] = "after" if commits else "before"


def _process_contender(path: str, barrier, results, marker: str) -> None:
    backend = SQLiteTestBackend(Path(path))
    barrier.wait(timeout=10)
    try:
        backend.compare_and_swap(
            "process-binding", expected_version=0, replacement={"version": 1, "marker": marker}
        )
        results.put("success")
    except DurableSecretBackendConflict:
        results.put("conflict")
    except Exception:
        results.put("unexpected")


class SQLiteTestBackendTests(unittest.TestCase):
    def test_reusable_conformance_with_new_clients(self):
        with TemporaryDirectory() as tmp:
            report = run_durable_backend_conformance(SQLiteFixture(Path(tmp) / "state.sqlite"))
        self.assertTrue(report.passed, report.to_safe_dict())
        self.assertTrue(all(report.to_safe_dict().values()))

    def test_two_processes_have_one_cas_winner_and_restart_reads_it(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite"
            SQLiteTestBackend(path).seed("process-binding", {"version": 0, "marker": "initial"})
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(2)
            results = context.Queue()
            processes = [
                context.Process(target=_process_contender, args=(str(path), barrier, results, marker))
                for marker in ("a", "b")
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=15)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            self.assertEqual([process.exitcode for process in processes], [0, 0])
            self.assertEqual(sorted(results.get(timeout=2) for _ in processes), ["conflict", "success"])
            record = SQLiteTestBackend(path).read("process-binding")
            self.assertEqual(record["version"], 1)
            self.assertIn(record["marker"], ("a", "b"))


if __name__ == "__main__":
    unittest.main()

"""One-shot, private historical preparation through the shared AgentRunner.

No fetch, review approval, model fitting, scheduler, DB or hosted runtime. A
completed task means its preparation report was verified, not that data qualify.
The caller owns the private local directory and later durable artifact storage.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

from ml.historical_training import digest, prepare, timestamp
from .adapters import Capability, ToolRegistry
from .model import ActionResult, ArtifactUpdate, StepSpec, TaskSpec
from .runner import AgentRunner, BlockedAction
from .store import FileStateStore

TASK_ID = "historical-preparation"
REPOSITORY = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode()


def write_once(path: Path, value) -> None:
    """Never replace an existing report, including a partial interrupted write."""
    content = encoded(value)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != content:
            raise BlockedAction("historical_output_conflict") from None
        return
    with os.fdopen(fd, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())


class HistoricalPreparationAdapter:
    """Paths and exact input hashes are host-bound, never selected by task args."""
    name = "historical-offline-preparation"

    def __init__(self, *, records: Path, reviews: Path, output: Path,
                 validation_start: str, test_start: str):
        self.records, self.reviews, self.output = records, reviews, output
        if timestamp(validation_start) >= timestamp(test_start):
            raise ValueError("validation_must_precede_test")
        self.inputs = {"records_sha256": file_hash(records), "reviews_sha256": file_hash(reviews),
                       "validation_start": validation_start, "test_start": test_start,
                       "split_purpose": "diagnostic_only", "training_enabled": False}

    def capabilities(self):
        return (Capability("historical.prepare", "write", ("historical:local:prepare",), False),
                Capability("historical.verify_preparation", "read", ("historical:local:read",), True))

    def actions(self):
        return {"historical.prepare": self.run, "historical.verify_preparation": self.verify}

    def expected_report(self):
        payloads = []
        for path, field in ((self.records, "records_sha256"), (self.reviews, "reviews_sha256")):
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != self.inputs[field]:
                raise BlockedAction("historical_input_changed")
            payloads.append(json.loads(raw))
        data, reviews = payloads
        if (not isinstance(data, dict) or data.get("schema_version") != "historical-review-records-v1"
                or not isinstance(data.get("records"), list)):
            raise BlockedAction("historical_review_records_required")
        rows = data["records"]
        hashes = {r["race_id"]: digest(r) for r in rows}
        if len(hashes) != len(rows) or data.get("record_hashes") != hashes:
            raise BlockedAction("historical_record_hashes_mismatch")
        report = prepare(rows, reviews, self.inputs["validation_start"], self.inputs["test_start"])
        report["preparation_inputs"] = dict(self.inputs)
        return report

    def check(self):
        expected = self.expected_report()
        if self.output.is_symlink() or self.output.read_bytes() != encoded(expected):
            raise BlockedAction("historical_preparation_readback_mismatch")
        return expected

    def run(self, args, context):
        if args or context.get("dry_run") is True:
            raise BlockedAction("historical_preparation_write_not_authorized")
        report = self.expected_report()
        write_once(self.output, report)
        self.check()
        return ActionResult(message="offline preparation report verified; no training performed",
            data={"partition_counts": report["partition_counts"], "excluded_records": len(report["excluded"]),
                  "training_runs": 0},
            artifacts=(ArtifactUpdate(artifact_id="historical-preparation-plan", kind="historical-plan",
                locator=str(self.output), created=True, verified=True, persistent_saved=False,
                metadata={"sha256": file_hash(self.output), "storage_scope": "local_host_only",
                          "training_runs": 0}),))

    def verify(self, args, context):
        self.check()
        return {"verified": True}


def run_preparation(records: Path, reviews: Path, run_dir: Path,
                    validation_start: str, test_start: str) -> dict:
    """Run or resume the same hash-bound task; changed inputs need a new directory.

    Interrupted/failed tasks retain AgentRunner's explicit reconciliation rule.
    Even a completed resume rechecks report bytes before reporting success.
    """
    records, reviews, root = records.resolve(), reviews.resolve(), run_dir.resolve()
    if root.is_relative_to(REPOSITORY):
        raise ValueError("historical_run_directory_must_be_outside_repository")
    output = root / "preparation.json"
    if any(p == output or p.is_relative_to(root / "state") or p == root / "task.json"
           for p in (records, reviews)):
        raise ValueError("historical_input_output_overlap")
    adapter = HistoricalPreparationAdapter(records=records, reviews=reviews, output=output,
                                          validation_start=validation_start, test_start=test_start)
    # Validate input contents before creating a new task directory.
    adapter.expected_report()
    registry = ToolRegistry()
    registry.register(adapter)
    spec = TaskSpec(task_id=TASK_ID, title="Historical preparation diagnostic",
        goal="Verify private preparation output without collecting, approving or training",
        allowed_actions=tuple(registry.actions()),
        inputs={**adapter.inputs, "records_path": str(records), "reviews_path": str(reviews)},
        steps=(StepSpec("prepare", "historical.prepare", verify_action="historical.verify_preparation"),),
        completion_conditions=("preparation bytes verified", "training remains off"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = FileStateStore(root / "state")
    with store.task_lock(TASK_ID):
        write_once(root / "task.json", spec.to_dict())
        if store.load_state(TASK_ID).status == "completed":
            adapter.check()
    outcome = AgentRunner(store, registry.actions()).run(spec)
    report = adapter.check() if outcome.status == "completed" else None
    return {"schema_version": "historical-agent-preparation-receipt-v1",
            "outcome": asdict(outcome), "inputs": adapter.inputs,
            "partition_counts": report["partition_counts"] if report else None,
            "excluded_records": len(report["excluded"]) if report else None,
            "preparation_sha256": file_hash(output) if report else None,
            "training_runs": 0, "production_enabled": False,
            "automatic_collection_enabled": False, "autonomous_learning_enabled": False,
            "split_purpose": "diagnostic_only", "durable_storage_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("reviews", type=Path)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--validation-start", required=True)
    parser.add_argument("--test-start", required=True)
    args = parser.parse_args()
    try:
        receipt = run_preparation(args.records, args.reviews, args.run_dir,
                                  args.validation_start, args.test_start)
    except Exception:
        # Private input/provider text must not become command logs.
        print(json.dumps({"status": "blocked", "reason": "historical_preparation_requires_review"}))
        return 2
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["outcome"]["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

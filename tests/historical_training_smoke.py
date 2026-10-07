"""Synthetic model execution, not evidence of real-race accuracy."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.historical_training import prepare, train
from test_historical_training import fixture, review


def main():
    records = [fixture(day, 7 if day % 2 else 9) for day in range(1, 13)]
    for i, record in enumerate(records):
        record["trifecta_outcomes"] = [[1, 2, 3] if i % 2 else [3, 2, 1]]
    plan = prepare(records, [review(r) for r in records],
                   "2020-01-09T00:00:00+09:00", "2020-01-11T00:00:00+09:00")
    with TemporaryDirectory() as root:
        output = Path(root) / "models"
        result = train(plan, output)
        assert result["training_runs"] == 1
        assert result["test_metrics"]["validation_races"] == 2
        assert not result["production_enabled"] and not result["prospective"]
        assert {r["race_id"] for r in result["test_metrics"]["per_race"]} == {"synthetic-11", "synthetic-12"}
        assert all((output / (p + ".txt")).is_file() for p in ("first", "second", "third"))
        assert json.loads((output / "dataset_manifest.json").read_text())["partition_counts"] == {
            "train": 8, "validation": 2, "test": 2}
    print("PASS: synthetic historical model training and held-out evaluation (7/9 riders)")


if __name__ == "__main__":
    main()

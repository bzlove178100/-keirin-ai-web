"""Synthetic model execution, not evidence of real-race accuracy."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.historical_training import prepare, train
from ml.historical_form import build
from test_historical_training import fixture, review


def main():
    records = [fixture(day, 3 + day % 7) for day in range(1, 19)]
    for i, record in enumerate(records):
        record["trifecta_outcomes"] = [[1, 2, 3] if i % 2 else [3, 2, 1]]
    history = []
    for record in records:
        order = record["trifecta_outcomes"][0] + list(range(4, record["rider_count"] + 1))
        history.append({"race_id": record["race_id"], "race_status": "completed",
                        "race_start_at": record["listed_scheduled_start_jst"],
                        "result_available_at": record["result_available_at"],
                        **{k: "synthetic evidence" for k in ("identity_evidence", "result_time_evidence", "source_use_evidence")},
                        "participants": [{"car_number": car, "rider_id": f"synthetic:rider-{car}",
                                          "finish_rank": rank, "status": "FINISHED"}
                                         for rank, car in enumerate(order, 1)]})
    for record in records:
        target = {"race_id": record["race_id"], "feature_as_of": record["feature_as_of"],
                  "listed_scheduled_start_jst": record["listed_scheduled_start_jst"],
                  "identity_evidence": "synthetic", "entry_time_evidence": "synthetic",
                  "riders": [{"car_number": r["car_number"], "rider_id": f"synthetic:rider-{r['car_number']}"}
                             for r in record["riders"]]}
        form = build(target, history)
        for feature, candidate in zip(record["pre_race_features"], form["riders"]):
            assert feature["car_number"] == candidate["car_number"]
            feature.update(candidate["features"])
        # Preserve derivation before the exact combined record is reviewed.
        record["derived_form_provenance"] = form
    plan = prepare(records, [review(r) for r in records],
                   "2020-01-09T00:00:00+09:00", "2020-01-12T00:00:00+09:00")
    with TemporaryDirectory() as root:
        output = Path(root) / "models"
        result = train(plan, output)
        assert result["training_runs"] == 1
        assert result["test_metrics"]["validation_races"] == 7
        assert set(result["test_metrics_by_rider_count"]) == set(map(str, range(3, 10)))
        assert not result["production_enabled"] and not result["prospective"]
        assert {r["race_id"] for r in result["test_metrics"]["per_race"]} == {f"synthetic-{n}" for n in range(12, 19)}
        assert all((output / (p + ".txt")).is_file() for p in ("first", "second", "third"))
        assert json.loads((output / "dataset_manifest.json").read_text())["partition_counts"] == {
            "train": 8, "validation": 3, "test": 7}
    print("PASS: synthetic historical form -> model training -> held-out evaluation (3-9 riders)")


if __name__ == "__main__":
    main()

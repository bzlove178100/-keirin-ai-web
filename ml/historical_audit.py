"""Offline intake audit. Does not fetch, train, or relabel history as prospective.

Input is curated historical-source observations, not trusted provenance proof.
All rows remain quarantined here; a separate reviewed historical path is required.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(records: list[dict]) -> dict:
    seen: dict[str, dict] = {}
    conflicts: set[str] = set()
    duplicates = 0
    problems: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            problems.append({"race_id": None, "reasons": ["invalid_record"]})
            continue
        key = record.get("race_id")
        if not isinstance(key, str) or not key.strip():
            problems.append({"race_id": None, "reasons": ["race_id_missing"]})
            continue
        if key in seen:
            # Do not count the same race from two websites as two examples.
            a = {k: v for k, v in seen[key].items() if k != "sources"}
            b = {k: v for k, v in record.items() if k != "sources"}
            if a == b:
                duplicates += 1
            else:
                conflicts.add(key)
            continue
        seen[key] = record

    rows = []
    for key, record in seen.items():
        reasons = ["dedicated_historical_review_required"]
        if key in conflicts:
            reasons.append("conflicting_duplicate_requires_review")
        count = record.get("rider_count")
        if type(count) is not int or not 3 <= count <= 9:
            reasons.append("invalid_rider_count")
        sources = record.get("sources")
        if not isinstance(sources, list) or not sources:
            reasons.append("source_missing")
        if record.get("training_use_status") != "confirmed":
            reasons.append("training_use_unconfirmed")
        if record.get("pre_race_state_verified") is not True:
            reasons.append("historical_feature_time_unverified")
        riders = record.get("riders")
        cars = [r.get("car_number") for r in riders if isinstance(r, dict)] if isinstance(riders, list) else []
        if (not isinstance(riders, list) or len(cars) != len(riders)
                or len(cars) != count
                or any(type(c) is not int or not 1 <= c <= 9 for c in cars)
                or len(set(c for c in cars if type(c) is int)) != len(cars)):
            reasons.append("roster_incomplete_or_invalid")
        outcomes = record.get("trifecta_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            reasons.append("outcome_missing")
        elif len(outcomes) != 1 or record.get("dead_heat") is True:
            reasons.append("dead_heat_requires_multilabel_contract")
        else:
            combo = outcomes[0]
            if (not isinstance(combo, list) or len(combo) != 3
                    or any(type(c) is not int or not 1 <= c <= 9 for c in combo)
                    or len(set(c for c in combo if type(c) is int)) != 3):
                reasons.append("invalid_outcome")
            elif cars and not set(combo).issubset(set(c for c in cars if type(c) is int)):
                reasons.append("outcome_not_in_roster")
        rows.append({"race_id": key, "rider_count": count,
                     "status": "quarantined", "reasons": reasons,
                     "supervised_training_eligible": False,
                     "prospective": False})
    return {"schema_version": "historical-intake-audit-v1",
            "input_records": len(records), "unique_races": len(seen),
            "identical_duplicates": duplicates, "conflicting_races": len(conflicts),
            "invalid_records": problems, "quarantined_races": len(rows),
            "training_eligible_races": 0, "training_runs": 0,
            "automatic_collection_enabled": False, "production_enabled": False,
            "rider_count_distribution": dict(Counter(str(r["rider_count"]) for r in rows)),
            "records": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        parser.error("input must have a records array")
    result = audit(records)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

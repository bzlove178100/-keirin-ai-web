"""Join private KeirinDB entrant CSVs to payout candidates, entirely offline.

Observed card fields are not proof of pre-race availability. This conversion
does not approve training, resolve missing cars, or use a current rider master.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from ml.historical_training import digest

REQUIRED = {"Race_ID", "Car", "Player_ID", "Player_Name", "Status", "Style",
            "Points", "S", "H", "B"}
MAPPING = {"Points": "race_score", "S": "S", "H": "H", "B": "B"}


def load_entrants(path: Path) -> tuple[list[dict], dict]:
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    header = reader.fieldnames or []
    if len(header) != len(set(header)) or not REQUIRED.issubset(header):
        raise ValueError("invalid_entrant_header")
    rows, blank = [], 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("invalid_entrant_row_width")
        if not any(value.strip() for value in row.values()):
            blank += 1
            continue
        rows.append(row)
    return rows, {"filename": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                  "nonempty_rows": len(rows), "blank_rows_ignored": blank}


def _numeric(raw: str, column: str):
    if raw == "":
        return None
    pattern = r"[0-9]+(?:\.[0-9]+)?" if column == "Points" else r"[0-9]+"
    if not isinstance(raw, str) or not re.fullmatch(pattern, raw):
        raise ValueError("invalid_entrant_numeric:" + column)
    value = float(raw) if column == "Points" else int(raw)
    if not math.isfinite(value):
        raise ValueError("invalid_entrant_numeric:" + column)
    return value


def _features(record: dict, rows: list[dict]) -> list[dict]:
    if record.get("normalization_status") != "internally_consistent_candidate":
        raise ValueError("payout_candidate_not_normalized")
    participants = record["participants"]
    if not 3 <= len(rows) <= 9 or len(rows) != len(participants):
        raise ValueError("entrant_roster_incomplete")
    expected = {p["car_number"]: p for p in participants}
    results = {int(r["Car"]): r for r in record["raw"]["results"]}
    seen_cars, seen_ids, features = set(), set(), []
    for row in rows:
        if not REQUIRED.issubset(row) or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("invalid_entrant_row")
        if not re.fullmatch(r"[1-9]", row["Car"]):
            raise ValueError("entrant_car_missing_or_invalid")
        car, identity = int(row["Car"]), row["Player_ID"]
        if not re.fullmatch(r"[0-9]+", identity):
            raise ValueError("entrant_identity_missing_or_invalid")
        if car in seen_cars or identity in seen_ids:
            raise ValueError("duplicate_entrant_car_or_identity")
        seen_cars.add(car)
        seen_ids.add(identity)
        if car not in expected or expected[car]["rider_id"] != "keirindb:" + identity:
            raise ValueError("entrant_result_identity_mismatch")
        name, result_name = row["Player_Name"], results[car].get("Player_Name", "")
        if not name.strip() or not result_name.strip() or "".join(name.split()) != "".join(result_name.split()):
            raise ValueError("entrant_result_name_mismatch")
        if row["Status"] not in ("", "欠場") or (row["Status"] == "欠場") != (expected[car]["status"] == "DNS"):
            raise ValueError("entrant_result_withdrawal_mismatch")
        if row["Style"] not in ("逃", "両", "追"):
            raise ValueError("entrant_style_missing_or_invalid")
        features.append({"car_number": car, "style": row["Style"],
                         **{target: _numeric(row[source], source) for source, target in MAPPING.items()}})
    if seen_cars != set(expected):
        raise ValueError("entrant_roster_mismatch")
    return sorted(features, key=lambda f: f["car_number"])


def enrich(candidates: dict, entrants: list[dict]) -> dict:
    if candidates.get("schema_version") != "historical-payout-candidates-v1":
        raise ValueError("payout_candidate_report_required")
    records = candidates.get("records")
    if not isinstance(records, list) or not isinstance(entrants, list):
        raise ValueError("records_and_entrants_must_be_arrays")
    by_race, seen, duplicates = defaultdict(list), set(), 0
    for row in entrants:
        if not isinstance(row, dict) or not isinstance(row.get("Race_ID"), str) or not row["Race_ID"].strip():
            raise ValueError("entrant_race_id_missing")
        fingerprint = digest(row)
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        by_race[row["Race_ID"]].append(row)
    output, keys = [], set()
    for source in records:
        key = source.get("race_id")
        if not isinstance(key, str) or not key or key in keys:
            raise ValueError("missing_or_duplicate_candidate_race_id")
        keys.add(key)
        parent = source.get("candidate_sha256")
        if parent != digest({k: v for k, v in source.items() if k != "candidate_sha256"}):
            raise ValueError("payout_candidate_digest_mismatch")
        if source.get("pre_race_features"):
            raise ValueError("refusing_to_overwrite_existing_features")
        item = copy.deepcopy(source)
        rows = copy.deepcopy(by_race.get(key, []))
        item.update(parent_candidate_sha256=parent, raw_entrants=rows,
                    raw_entrants_sha256=digest(rows), entrant_join_status="quarantined",
                    entrant_join_reasons=[], pre_race_features=[], training_approved=False,
                    pre_race_state_verified=False)
        try:
            if not rows:
                raise ValueError("entrant_rows_missing")
            item["pre_race_features"] = _features(item, rows)
            item["entrant_join_status"] = "matched_unverified_features"
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            item["entrant_join_reasons"].append(str(exc))
        item.pop("candidate_sha256")
        item["candidate_sha256"] = digest(item)
        output.append(item)
    orphans = [{"race_id": key, "raw_entrants": by_race[key], "raw_entrants_sha256": digest(by_race[key])}
               for key in sorted(set(by_race) - keys)]
    features = [f for row in output for f in row["pre_race_features"]]
    return {"schema_version": "historical-entrant-candidates-v1", "records": output,
            "orphan_entrant_races": orphans,
            "summary": {"unique_races": len(output), "input_entrant_rows": len(entrants),
                        "identical_duplicate_rows_ignored": duplicates,
                        "join_status_counts": dict(Counter(r["entrant_join_status"] for r in output)),
                        "exclusion_reason_counts": dict(Counter(reason for r in output for reason in r["entrant_join_reasons"])),
                        "matched_rider_rows": len(features), "orphan_entrant_races": len(orphans),
                        "missing_numeric_values": {column: sum(f[column] is None for f in features) for column in MAPPING.values()},
                        "training_eligible_races": 0, "training_runs": 0},
            "feature_mapping": MAPPING, "feature_time_verified": False,
            "source_use_verified": False, "production_enabled": False,
            "automatic_collection_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--entrants", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, receipts = [], []
    for path in args.entrants:
        data, receipt = load_entrants(path)
        rows.extend(data)
        receipts.append(receipt)
    report = enrich(json.loads(args.candidates.read_text()), rows)
    report["source_files"] = receipts
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Convert entrant/payout candidates into unapproved historical review records.

Purely offline. Replays both normalizers against retained raw rows, preserves
settlement types and missing times, and never manufactures source-use reviews.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from ml.historical_entrants import enrich
from ml.historical_payouts import normalize
from ml.historical_training import digest


def convert(report: dict) -> dict:
    if not isinstance(report, dict) or report.get("schema_version") != "historical-entrant-candidates-v1":
        raise ValueError("entrant_candidate_report_required")
    candidates = report.get("records")
    if not isinstance(candidates, list):
        raise ValueError("candidate_records_array_required")
    input_hash, records, quarantine, seen = digest(report), [], [], set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid_candidate")
        key = candidate.get("race_id")
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise ValueError("missing_or_duplicate_candidate_race_id")
        seen.add(key)
        parent = candidate.get("candidate_sha256")
        if parent != digest({k: v for k, v in candidate.items() if k != "candidate_sha256"}):
            raise ValueError("candidate_digest_mismatch")
        if (candidate.get("normalization_status") != "internally_consistent_candidate"
                or candidate.get("entrant_join_status") != "matched_unverified_features"):
            quarantine.append({"race_id": key, "candidate_sha256": parent,
                               "reasons": ["normalized_matched_candidate_required"],
                               "upstream_reasons": copy.deepcopy(candidate.get("reasons", []) +
                                                                 candidate.get("entrant_join_reasons", []))})
            continue
        # Hashes detect accidental change; replay also checks derived values
        # against the supplied raw rows. Neither establishes source truth.
        raw = candidate.get("raw", {})
        replay = enrich(normalize(raw["info"], raw["results"], raw["payoffs"]),
                        candidate["raw_entrants"])["records"]
        if len(replay) != 1 or replay[0]["race_id"] != key:
            raise ValueError("candidate_raw_replay_identity_mismatch")
        expected = replay[0]
        fields = ("normalization_status", "entrant_join_status", "participants", "settlements",
                  "pre_race_features", "race_date", "venue", "race_number", "actual_starters",
                  "raw_sha256", "raw_entrants_sha256", "parent_candidate_sha256")
        if any(candidate.get(k) != expected.get(k) for k in fields):
            raise ValueError("candidate_raw_replay_mismatch")
        settlement = copy.deepcopy(expected["settlements"]["3連単"])
        record = {
            "race_id": key, "race_date": expected["race_date"], "venue": expected["venue"],
            "race_number": expected["race_number"],
            "rider_count": len(expected["participants"]),
            "riders": copy.deepcopy(expected["participants"]),
            "actual_starters": expected["actual_starters"],
            "pre_race_features": copy.deepcopy(expected["pre_race_features"]),
            "trifecta_outcomes": [x["combination"] for x in settlement["outcomes"]],
            "trifecta_settlement": settlement,
            "dead_heat": settlement["status"] == "dead_heat",
            "feature_as_of": candidate.get("feature_as_of"),
            "listed_scheduled_start_jst": candidate.get("listed_scheduled_start_jst"),
            "result_available_at": candidate.get("result_available_at"),
            "sources": [{"kind": "unverified_keirindb_import_candidate", "candidate_sha256": parent,
                         "input_report_sha256": input_hash, "raw_sha256": candidate["raw_sha256"],
                         "raw_entrants_sha256": candidate["raw_entrants_sha256"]}],
            "prospective": False, "pre_race_state_verified": False,
            "training_use_status": "unconfirmed", "training_approved": False,
            "conversion_status": "unapproved_historical_review_record",
        }
        records.append(record)
    return {"schema_version": "historical-review-records-v1", "records": records,
            "record_hashes": {r["race_id"]: digest(r) for r in records},
            "quarantined_records": quarantine, "input_report_sha256": input_hash,
            "orphan_entrant_races": copy.deepcopy(report.get("orphan_entrant_races", [])),
            "summary": {"input_races": len(candidates), "converted_records": len(records),
                        "quarantined_races": len(quarantine),
                        "settlement_counts": dict(Counter(r["trifecta_settlement"]["status"] for r in records)),
                        "rider_count_distribution": dict(Counter(str(r["rider_count"]) for r in records)),
                        "training_eligible_races": 0, "training_runs": 0},
            "production_enabled": False, "automatic_collection_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = convert(json.loads(args.input.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

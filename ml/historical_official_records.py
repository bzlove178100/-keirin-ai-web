"""Join saved pre-race and result captures into unapproved review records.

Both captures are replayed through the strict importer. No fetching, approval,
training, or retrospective replacement of a pre-race observation is performed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import unicodedata
from pathlib import Path

from ml.historical_official_detail import ingest
from ml.historical_training import digest, timestamp


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("rider_name_missing")
    return "".join(unicodedata.normalize("NFKC", value).split())


def join(pre_bytes: bytes, pre_receipt: dict, result_bytes: bytes,
         result_receipt: dict, race_date: str, venue_code: str,
         race_number: int) -> dict:
    pre = ingest(pre_bytes, pre_receipt, race_date, venue_code, race_number, "pre")
    result = ingest(result_bytes, result_receipt, race_date, venue_code, race_number, "result")
    if set(pre["issues"]) - {"pre_race_roster_note_requires_review"} or result["issues"]:
        raise ValueError("capture_issues_require_review")
    starts = pre["listed_start_times_jst"] + result["listed_start_times_jst"]
    if not timestamp(pre["observed_at"]) < min(map(timestamp, starts)):
        raise ValueError("pre_capture_not_before_all_observed_starts")
    if timestamp(result["observed_at"]) < max(map(timestamp, starts)):
        raise ValueError("result_capture_before_observed_start")
    before = {r["car_number"]: r for r in pre["summary"]["rider_rows"]}
    after = {r["car_number"]: r for r in result["summary"]["rider_rows"]}
    if set(before) != set(after):
        raise ValueError("cross_capture_roster_mismatch")
    for car in before:
        if (before[car]["rider_id"] != after[car]["rider_id"]
                or _name(before[car]["name_as_observed"]) != _name(after[car]["name_as_observed"])):
            raise ValueError("cross_capture_rider_identity_mismatch")
    pre_withdrawn = {c for c, r in before.items()
                     if unicodedata.normalize("NFKC", r["roster_note_as_observed"]).strip() == "(欠場)"}
    result_withdrawn = set(result["summary"]["withdrawn_cars"])
    # A result-only withdrawal must not redefine the feature-time population.
    if pre_withdrawn != result_withdrawn:
        raise ValueError("withdrawal_changed_after_pre_capture_requires_review")
    active = sorted(set(before) - pre_withdrawn)
    if not 3 <= len(active) <= 9:
        raise ValueError("unsupported_active_roster")
    if result["summary"]["confirmed_starter_count"] != len(active):
        raise ValueError("unknown_or_mismatched_starter_classification")
    if result["summary"]["repeated_finish_ranks_observed"]:
        raise ValueError("dead_heat_requires_multilabel_contract")
    ranks = sorted(r["finish_position"] for r in after.values() if r["finish_position"] is not None)
    if ranks != list(range(1, len(ranks) + 1)):
        raise ValueError("noncontiguous_finish_order_requires_review")
    top = result["summary"].get("trifecta", [])
    if len(top) != 1 or not set(top[0]["cars"]).issubset(active):
        raise ValueError("single_active_outcome_required")
    features = []
    for car in active:
        row = before[car]
        if row["style_as_observed"] not in ("逃", "両", "追"):
            raise ValueError("unknown_pre_race_style")
        value = row["score_as_observed"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("pre_race_score_missing")
        score = float(value)
        if not math.isfinite(score) or not 0 <= score <= 150:
            raise ValueError("invalid_pre_race_score")
        # Statistics with unconfirmed definitions/windows stay in raw observations.
        features.append({"car_number": car, "style": row["style_as_observed"],
                         "race_score": score, "S": None, "H": None, "B": None})
    record = {
        "race_id": f"{race_date.replace('-', '')}_keirin_{venue_code}_{race_number}",
        "race_date": race_date, "venue_code": venue_code, "race_number": race_number,
        "rider_count": len(active),
        "riders": [{"car_number": c, "rider_id": before[c]["rider_id"],
                    "name": before[c]["name_as_observed"]} for c in active],
        "listed_rider_count": len(before), "pre_race_withdrawn_cars": sorted(pre_withdrawn),
        "actual_starters": result["summary"]["confirmed_starter_count"],
        "pre_race_features": features, "feature_as_of": pre["observed_at"],
        "listed_scheduled_start_jst": min(starts, key=timestamp),
        "result_available_at": result["observed_at"],
        "result_time_basis": "known_by_capture_completion_not_exact_publication",
        "trifecta_outcomes": [copy.deepcopy(top[0]["cars"])],
        "trifecta_payouts_yen": [top[0]["payout_yen"]], "dead_heat": False,
        "sources": [pre["source_url"]],
        "source_observations": {"pre": pre, "result": result},
        "prospective": False, "pre_race_state_verified": False,
        "training_use_status": "unconfirmed", "training_approved": False,
        "conversion_status": "unapproved_historical_review_record",
        "remaining": ["source_use_review", "feature_definition_and_roster_review",
                      "final_record_hash_review"],
    }
    return record


def convert(pairs: list[dict]) -> dict:
    """Fail duplicate identities; quarantine a bad pair without losing good ones."""
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("nonempty_capture_pairs_required")
    records, quarantined, seen = [], [], set()
    for pair in pairs:
        scope = (pair["race_date"], pair["venue_code"], pair["race_number"])
        if scope in seen:
            raise ValueError("duplicate_capture_pair")
        seen.add(scope)
        try:
            records.append(join(pair["pre_bytes"], pair["pre_receipt"],
                                pair["result_bytes"], pair["result_receipt"], *scope))
        except (ValueError, KeyError, TypeError) as exc:
            quarantined.append({"race_date": scope[0], "venue_code": scope[1],
                                "race_number": scope[2], "reason": str(exc),
                                "capture_hashes": {mode: hashlib.sha256(pair[mode + "_bytes"]).hexdigest()
                                                   for mode in ("pre", "result")},
                                "capture_receipts": {mode: copy.deepcopy(pair[mode + "_receipt"])
                                                     for mode in ("pre", "result")}})
    return {"schema_version": "historical-review-records-v1", "records": records,
            "record_hashes": {r["race_id"]: digest(r) for r in records},
            "quarantined_records": quarantined,
            "summary": {"input_pairs": len(pairs), "converted_records": len(records),
                        "quarantined_pairs": len(quarantined), "training_eligible_races": 0,
                        "training_runs": 0},
            "production_enabled": False, "automatic_collection_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pairs = []
    for entry in manifest["pairs"]:
        pair = {k: entry[k] for k in ("race_date", "venue_code", "race_number")}
        for mode in ("pre", "result"):
            path = args.manifest.parent / entry[mode + "_html"]
            receipt = args.manifest.parent / entry[mode + "_receipt"]
            pair[mode + "_bytes"] = path.read_bytes()
            pair[mode + "_receipt"] = json.loads(receipt.read_text(encoding="utf-8"))
        pairs.append(pair)
    report = convert(pairs)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()

"""Reconstruct recent form from reviewed results available before a historical cutoff.

Outputs are feature candidates, not training approval. Evidence references are
operator attestations. This module does not fetch sources or infer publication times.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ml.historical_training import digest, timestamp

FORM_FEATURES = ("recent_win_rate", "recent_top2_rate", "recent_top3_rate", "recent_avg_finish")


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _roster(rows: list) -> None:
    if not isinstance(rows, list) or not 3 <= len(rows) <= 9:
        raise ValueError("invalid_roster_size")
    cars, identities = [], []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_rider")
        car, identity = row.get("car_number"), row.get("rider_id")
        if type(car) is not int or not 1 <= car <= 9:
            raise ValueError("invalid_car_number")
        if not _text(identity) or ":" not in identity or not all(_text(s) for s in identity.split(":", 1)):
            raise ValueError("namespaced_rider_identity_required")
        cars.append(car)
        identities.append(identity)
    if len(set(cars)) != len(cars) or len(set(identities)) != len(identities):
        raise ValueError("duplicate_car_or_rider_identity")


def build(target: dict, history: list, window_days: int = 120) -> dict:
    if type(window_days) is not int or window_days <= 0:
        raise ValueError("positive_window_days_required")
    if not isinstance(target, dict) or not _text(target.get("race_id")):
        raise ValueError("target_race_id_required")
    if not isinstance(history, list):
        raise ValueError("history_array_required")
    for field in ("identity_evidence", "entry_time_evidence"):
        if not _text(target.get(field)):
            raise ValueError(field + "_required")
    cutoff = timestamp(target.get("feature_as_of"))
    if cutoff >= timestamp(target.get("listed_scheduled_start_jst")):
        raise ValueError("cutoff_must_precede_start")
    entrants = target.get("riders")
    _roster(entrants)
    lower = cutoff - window_days * 86400
    seen, conflicts, excluded = {}, set(), []
    duplicates = 0
    for record in history:
        if not isinstance(record, dict) or not _text(record.get("race_id")):
            excluded.append({"race_id": None, "reason": "invalid_history_record"})
            continue
        key = record["race_id"]
        if key in seen:
            if record == seen[key]:
                duplicates += 1
            else:
                conflicts.add(key)
        else:
            seen[key] = record
    usable = []
    for key, record in seen.items():
        try:
            if key == target["race_id"]:
                raise ValueError("target_result_excluded")
            if key in conflicts:
                raise ValueError("conflicting_history_race")
            if record.get("race_status") != "completed":
                raise ValueError("completed_race_required")
            for field in ("result_time_evidence", "identity_evidence", "source_use_evidence"):
                if not _text(record.get(field)):
                    raise ValueError(field + "_required")
            start = timestamp(record.get("race_start_at"))
            available = timestamp(record.get("result_available_at"))
            if available < start:
                raise ValueError("result_precedes_race")
            if not lower <= start < cutoff:
                raise ValueError("outside_race_window")
            if available >= cutoff:
                raise ValueError("result_not_available_before_cutoff")
            participants = record.get("participants")
            _roster(participants)
            ranks = []
            for rider in participants:
                status, rank = rider.get("status"), rider.get("finish_rank")
                if status == "FINISHED":
                    if type(rank) is not int or not 1 <= rank <= len(participants):
                        raise ValueError("invalid_finish_rank")
                    ranks.append(rank)
                elif status not in ("DNF", "DSQ", "DNS") or rank is not None:
                    raise ValueError("invalid_finish_status")
            # Competition ranks preserve ties (1, 1, 3), not arbitrary ordering.
            next_rank = 1
            for rank, count in sorted(Counter(ranks).items()):
                if rank != next_rank:
                    raise ValueError("incomplete_or_invalid_finish_order")
                next_rank += count
            digest(record)  # Reject non-serializable / non-finite provenance before aggregation.
            usable.append((start, key, record))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            excluded.append({"race_id": key, "reason": str(exc)})
    usable.sort(key=lambda item: (item[0], item[1]))
    rows = []
    provenance = {}
    for entrant in entrants:
        observations = []
        for _, key, record in usable:
            rider = next((p for p in record["participants"] if p["rider_id"] == entrant["rider_id"]), None)
            if rider is None or rider["status"] == "DNS":
                continue
            observations.append((key, rider))
            provenance[key] = {"race_id": key, "record_sha256": digest(record),
                               "result_available_at": record["result_available_at"],
                               **{f: record[f] for f in ("result_time_evidence", "identity_evidence", "source_use_evidence")}}
        n = len(observations)
        ranked = [p["finish_rank"] for _, p in observations if p["status"] == "FINISHED"]
        values = {"recent_win_rate": 100 * sum(r == 1 for r in ranked) / n if n else None,
                  "recent_top2_rate": 100 * sum(r <= 2 for r in ranked) / n if n else None,
                  "recent_top3_rate": 100 * sum(r <= 3 for r in ranked) / n if n else None,
                  "recent_avg_finish": sum(ranked) / len(ranked) if ranked else None}
        rows.append({"car_number": entrant["car_number"], "rider_id": entrant["rider_id"],
                     "features": values, "starts": n, "classified_finishes": len(ranked),
                     "status_counts": dict(Counter(p["status"] for _, p in observations)),
                     "history_race_ids": [key for key, _ in observations]})
    return {"schema_version": "historical-form-candidates-v1", "target_race_id": target["race_id"],
            "target_sha256": digest(target), "feature_as_of": target["feature_as_of"],
            "window_days": window_days, "riders": rows, "provenance": list(provenance.values()),
            "excluded_history": excluded, "identical_duplicates": duplicates,
            "rate_units": "percent_of_started_races", "average_finish_denominator": "classified_finishes_only",
            "history_coverage": "supplied_records_only_not_complete_career",
            "training_approved": False, "prospective": False, "training_runs": 0,
            "production_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("history", type=Path)
    parser.add_argument("--window-days", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.target.read_text()), json.loads(args.history.read_text()), args.window_days)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"riders": len(result["riders"]), "history_used": len(result["provenance"]),
                      "excluded_history": len(result["excluded_history"]), "training_runs": 0}))


if __name__ == "__main__":
    main()

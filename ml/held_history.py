"""Offline Phase32 result holds. No winner, training label, DB write or override."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import re

try:
    from .settle_snapshot import validate_snapshot, _snapshot_times, _iso
except ImportError:
    from settle_snapshot import validate_snapshot, _snapshot_times, _iso

HELD_SCHEMA = "phase32-held-history-v1"
HELD_STATUSES = ("dead_heat", "withdrawn", "cancelled")


def build_held_history(snapshot: dict, settlement: dict) -> dict:
    validate_snapshot(snapshot)
    engine = snapshot["engine_response"]
    if any(value is not None and value != "phase32-hit-priority-all210-v1" for value in
           (engine.get("engine_candidate"), (engine.get("architecture") or {}).get("engine"))):
        raise ValueError("engine_version_mismatch")
    if not isinstance(settlement, dict) or settlement.get("result_status") not in HELD_STATUSES:
        raise ValueError("held_result_status_invalid")
    status = settlement["result_status"]
    fields = {"result_status", "result_timestamp"}
    if status == "withdrawn":
        fields.add("withdrawn_car_numbers")
    if set(settlement) != fields:
        raise ValueError("held_settlement_fields_invalid")
    captured, scheduled = _snapshot_times(snapshot)
    observed = _iso(settlement["result_timestamp"], "result_timestamp")
    if observed < captured:
        raise ValueError("result_before_capture")
    if status == "dead_heat" and observed < scheduled:
        raise ValueError("result_before_scheduled_start")
    if status == "withdrawn":
        cars = settlement["withdrawn_car_numbers"]
        roster = {p["car_number"] for p in snapshot["race_data"]["players"]}
        if (not isinstance(cars, list) or not cars or
                any(type(c) is not int or c not in roster for c in cars) or len(set(cars)) != len(cars)):
            raise ValueError("withdrawn_cars_invalid")
    race = snapshot["race_data"]["race"]
    if (not isinstance(race.get("date"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", race["date"]) or
            not isinstance(race.get("venue"), str) or not race["venue"].strip() or
            type(race.get("race_number")) is not int or not 1 <= race["race_number"] <= 12):
        raise ValueError("held_race_identity_invalid")
    return {
        "schema_version": HELD_SCHEMA,
        "race_id": f"{race['date']}-{race['venue']}-{race['race_number']}R",
        "prediction_timestamp": snapshot["captured_at"],
        "snapshot": deepcopy(snapshot), "settlement": deepcopy(settlement),
        "evaluation_eligible": False, "supervised_training_eligible": False,
        "db_write_enabled": False, "external_fetch_enabled": False,
        "production_prediction_enabled": False, "monetary_ev_enabled": False,
    }


def validate_held_history(record: dict) -> None:
    if not isinstance(record, dict) or record.get("schema_version") != HELD_SCHEMA:
        raise ValueError("held_schema_mismatch")
    expected = build_held_history(record.get("snapshot"), record.get("settlement"))
    # JSON equality also distinguishes bool from number, unlike Python dict equality.
    if json.dumps(record, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError("held_record_mismatch")


def partition_holds(records: list[dict]) -> tuple[list[dict], dict, list[str]]:
    """Validate holds first, then suppress every ordinary record of the same race."""
    held = set()
    ordinary = []
    excluded = Counter()
    for record in records:
        if isinstance(record, dict) and record.get("schema_version") == HELD_SCHEMA:
            try:
                validate_held_history(record)
                held.add(record["race_id"])
                excluded["held_result"] += 1
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                excluded["invalid_held_record"] += 1
        else:
            ordinary.append(record)
    kept = []
    for record in ordinary:
        if isinstance(record, dict) and isinstance(record.get("race_id"), str) and record["race_id"] in held:
            excluded["race_has_held_result"] += 1
        else:
            kept.append(record)
    return kept, dict(excluded), sorted(held)


def normal_result_declared(record: dict) -> bool:
    """Reject unsupported result annotations instead of silently treating them as labels."""
    for part in (record, record.get("metadata") or {}):
        if not isinstance(part, dict):
            return False
        if part.get("schema_version") in (HELD_SCHEMA, "ml-held-history-v1"):
            return False
        if "result_status" in part and part["result_status"] != "normal":
            return False
        if any(key in part for key in ("dead_heat", "withdrawn_car_numbers", "trifecta_outcomes", "settlement")):
            return False
    return True

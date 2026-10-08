"""Offline, lossless detailed CSV intake and reviewed rate-feature bridge.

This is a source-specific intake, not a crawler. Unknown columns remain data,
never instructions or automatically admitted model features. No source-use or
historical-time evidence is inferred from a download time or file name.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from ml.historical_entrants import enrich
from ml.historical_payouts import normalize
from ml.historical_records import convert
from ml.historical_training import digest, timestamp

CATALOG = {
    "info": "Race_ID Date Venue Race_Grade Program_Name Race_Timezone Race_Number Class Program Unit Weather Wind_Speed Race_Status".split(),
    "entrants": "Race_ID Frame Car Status Player_Name Player_ID Points S B H Style Nige_Count Makuri_Count Sashi_Count Mark_Count Win_Count Second_Count Third_Count Out_Count Win_Rate Top2_Rate Top3_Rate Gear_Ratio Grade_Class Age Term Prefecture".split(),
    "results": "Race_ID Rank Status Car Player_Name Player_ID Gap Lap_Time Decision SB".split(),
    "payoffs": "Race_ID Bet_Type Outcome Payout Popularity".split(),
}
INT_FIELDS = set("Frame Car S B H Nige_Count Makuri_Count Sashi_Count Mark_Count Win_Count Second_Count Third_Count Out_Count Age Term Race_Number Unit".split())
FLOAT_FIELDS = {"Points", "Win_Rate", "Top2_Rate", "Top3_Rate", "Gear_Ratio", "Wind_Speed"}
RATE_MAP = {"Win_Rate": "recent_win_rate", "Top2_Rate": "recent_top2_rate", "Top3_Rate": "recent_top3_rate"}
UNSUPPLIED_GROUPS = ["pre_race_lineup", "rider_comments", "timestamped_odds", "bank_geometry",
                     "timestamped_pre_race_weather", "race_video", "training_and_equipment_changes"]


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def load_sources(manifest: dict, root: Path) -> list[dict]:
    """Explicit local files only; verify exact bytes before parsing all columns."""
    if manifest.get("schema_version") != "historical-detail-manifest-v1":
        raise ValueError("detail_manifest_required")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("source_files_required")
    sources, seen = [], set()
    root = root.resolve()
    for spec in manifest["files"]:
        if not isinstance(spec, dict) or spec.get("role") not in CATALOG:
            raise ValueError("unsupported_source_role")
        role = spec["role"]
        if spec.get("provider") != "keirindb":
            raise ValueError("unsupported_provider")
        relative = spec.get("path")
        if not _text(relative) or Path(relative).is_absolute():
            raise ValueError("relative_source_path_required")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("source_outside_root_or_missing")
        url = urlsplit(spec.get("source_url", ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("public_source_url_required")
        if spec.get("observed_at") is not None:
            timestamp(spec["observed_at"])
        if not _text(spec.get("observation_evidence")):
            raise ValueError("observation_evidence_required")
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != spec.get("sha256"):
            raise ValueError("source_digest_mismatch")
        identity = (role, sha)
        if identity in seen:
            raise ValueError("duplicate_source_file")
        seen.add(identity)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        columns = reader.fieldnames or []
        if (not columns or "Race_ID" not in columns or len(set(columns)) != len(columns)
                or any(not c.strip() for c in columns)):
            raise ValueError("invalid_detail_header")
        rows, blanks = [], 0
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("invalid_detail_row_width")
            if not any(v.strip() for v in row.values()):
                blanks += 1
                continue
            # Includes the original CSV row, source byte hash and physical end line.
            rows.append({"raw": row, "line_end": reader.line_num})
        sources.append({"role": role, "provider": "keirindb", "sha256": sha,
                        "source_url": spec["source_url"], "observed_at": spec.get("observed_at"),
                        "observation_evidence": spec["observation_evidence"],
                        "columns": columns, "rows": rows, "blank_rows_ignored": blanks})
    return sources


def _cell(column, value):
    if value is None:
        return {"state": "absent", "value": None}
    if value == "":
        return {"state": "blank", "value": None}
    if column in INT_FIELDS | FLOAT_FIELDS:
        pattern = r"[0-9]+" if column in INT_FIELDS else r"[0-9]+(?:\.[0-9]+)?"
        if not re.fullmatch(pattern, value):
            return {"state": "invalid", "value": None}
        try:
            number = int(value) if column in INT_FIELDS else float(value)
            if not math.isfinite(number) or (column in RATE_MAP and not 0 <= number <= 100):
                raise ValueError("invalid_numeric")
        except (ValueError, OverflowError):
            return {"state": "invalid", "value": None}
        return {"state": "value", "value": number}
    return {"state": "value", "value": value}


def _key(role, raw):
    fields = {"info": ("Race_ID",), "entrants": ("Race_ID", "Car"),
              "results": ("Race_ID", "Car"), "payoffs": ("Race_ID", "Bet_Type", "Outcome")}[role]
    return tuple(raw.get(f, "") for f in fields)


def collect(manifest: dict, root: Path) -> dict:
    sources = load_sources(manifest, root)
    unique, coverage, invalid_ids = {}, {}, []
    for source in sources:
        role = source["role"]
        for item in source["rows"]:
            raw = item["raw"]
            fingerprint = digest({"role": role, "raw": raw})
            origin = {k: source[k] for k in ("sha256", "source_url", "observed_at", "observation_evidence")}
            origin["line_end"] = item["line_end"]
            if fingerprint in unique:
                unique[fingerprint]["origins"].append(origin)
                continue
            cells = {c: _cell(c, raw.get(c)) for c in sorted(set(CATALOG[role]) | set(raw))}
            row = {"role": role, "raw": raw, "raw_row_sha256": digest(raw), "cells": cells,
                   "origins": [origin], "quarantine_reasons": []}
            if not raw["Race_ID"].strip():
                row["quarantine_reasons"].append("race_id_missing")
                invalid_ids.append(fingerprint)
            if role in ("entrants", "results") and not re.fullmatch(r"[1-9]", raw.get("Car", "")):
                row["quarantine_reasons"].append("car_missing_or_invalid")
            if any(cell["state"] == "invalid" for cell in cells.values()):
                row["quarantine_reasons"].append("invalid_numeric_detail")
            for column, cell in cells.items():
                coverage.setdefault(role + "." + column, Counter())[cell["state"]] += 1
            unique[fingerprint] = row
    groups = defaultdict(list)
    for row in unique.values():
        groups[(row["role"], _key(row["role"], row["raw"]))].append(row)
    conflicts = []
    for (role, key), rows in groups.items():
        if len(rows) > 1:
            conflicts.append({"role": role, "key": list(key), "raw_hashes": [r["raw_row_sha256"] for r in rows]})
            for row in rows:
                row["quarantine_reasons"].append("conflicting_logical_key")
    races = defaultdict(lambda: {role: [] for role in CATALOG})
    for row in unique.values():
        if row["raw"]["Race_ID"].strip():
            races[row["raw"]["Race_ID"]][row["role"]].append(row)
    records, backlog = [], []
    for key, tables in sorted(races.items()):
        missing_roles = [role for role, rows in tables.items() if not rows]
        issues = sorted({reason for rows in tables.values() for row in rows for reason in row["quarantine_reasons"]})
        record = {"race_id": key, "provider": "keirindb", "source_race_id": key, "tables": tables,
                  "missing_roles": missing_roles, "quarantine_reasons": issues,
                  "feature_as_of": None, "result_available_at": None,
                  "training_approved": False, "prospective": False}
        records.append(record)
        backlog.append({"race_id": record["race_id"], "missing_roles": missing_roles,
                        "unavailable_detail_groups": UNSUPPLIED_GROUPS,
                        "quality_issues": issues,
                        "required_evidence": ["source_use", "feature_availability", "scheduled_start", "result_availability"],
                        "automatic_fetch_authorized": False})
    # Retain orphan/bad-ID data as well, rather than silently deleting them.
    quarantined_unassigned = [unique[k] for k in invalid_ids]
    return {"schema_version": "historical-detail-intake-v1", "manifest_sha256": digest(manifest),
            "sources": [{k: v for k, v in s.items() if k != "rows"} for s in sources],
            "records": records, "unassigned_rows": quarantined_unassigned, "conflicts": conflicts,
            "field_coverage": {k: dict(v) for k, v in sorted(coverage.items())},
            "collection_backlog": backlog,
            "record_hashes": {r["race_id"]: digest(r) for r in records},
            "summary": {"source_files": len(sources), "race_observations": len(records),
                        "source_rows": sum(len(s["rows"]) for s in sources), "unique_rows": len(unique),
                        "duplicate_rows": sum(len(r["origins"]) - 1 for r in unique.values()),
                        "rows_by_role": dict(Counter(r["role"] for r in unique.values())),
                        "fields_by_role": {role: len({c for s in sources if s["role"] == role for c in s["columns"]}) for role in CATALOG},
                        "conflicting_keys": len(conflicts),
                        "races_with_all_four_tables": sum(not r["missing_roles"] for r in records),
                        "races_with_quality_issues": sum(bool(r["quarantine_reasons"]) for r in records),
                        "training_eligible_races": 0, "training_runs": 0},
            "scope": "supplied_files_only_not_all_details_or_continuous_history",
            "production_enabled": False, "automatic_collection_enabled": False,
            "autonomous_learning_running": False}


def review_records(detail: dict) -> dict:
    """Connect conflict-free full tables to existing strict normalization/review."""
    if detail.get("schema_version") != "historical-detail-intake-v1":
        raise ValueError("detail_intake_required")
    tables = {role: [] for role in CATALOG}
    held = []
    for record in detail["records"]:
        if detail["record_hashes"].get(record["race_id"]) != digest(record):
            raise ValueError("detail_record_changed")
        if record["quarantine_reasons"]:
            held.append({"race_id": record["race_id"], "reasons": record["quarantine_reasons"]})
            continue
        for role in CATALOG:
            tables[role].extend(row["raw"] for row in record["tables"][role])
    report = convert(enrich(normalize(tables["info"], tables["results"], tables["payoffs"]), tables["entrants"]))
    report["detail_intake_sha256"] = digest(detail)
    report["detail_quarantined_records"] = held
    report["summary"]["detail_quarantined_races"] = len(held)
    return report


def attach_reviewed_rates(record: dict, detail_record: dict, review: dict) -> dict:
    """Optional, hash-bound interpretation of three archive rates for training.

    A declaration of the source's denominator and window is required. This is
    an operator attestation, not independent fact verification. The final
    training review still needs the NEW record hash and the existing gates.
    """
    if review.get("record_sha256") != digest(record) or review.get("detail_sha256") != digest(detail_record):
        raise ValueError("rate_review_hash_mismatch")
    if record["race_id"] != detail_record["race_id"] or detail_record["quarantine_reasons"]:
        raise ValueError("rate_detail_identity_or_quality_mismatch")
    for field in ("reviewer", "rate_definition_evidence", "feature_time_evidence"):
        if not _text(review.get(field)):
            raise ValueError(field + "_required")
    if review.get("denominator") != "started_races" or review.get("unit") != "percent":
        raise ValueError("unsupported_rate_definition")
    lower, upper = timestamp(review.get("window_start")), timestamp(review.get("window_end"))
    cutoff = timestamp(record.get("feature_as_of"))
    if not lower < upper <= cutoff < timestamp(record.get("listed_scheduled_start_jst")):
        raise ValueError("rate_window_must_precede_prediction")
    rows = {int(r["raw"]["Car"]): r for r in detail_record["tables"]["entrants"]}
    riders = {r["car_number"]: r for r in record["riders"]}
    if len(rows) != len(detail_record["tables"]["entrants"]) or set(rows) != set(riders):
        raise ValueError("rate_roster_mismatch")
    result = copy.deepcopy(record)
    if {f["car_number"] for f in result["pre_race_features"]} != set(rows):
        raise ValueError("rate_feature_roster_mismatch")
    for feature in result["pre_race_features"]:
        car = feature["car_number"]
        row = rows[car]
        if "keirindb:" + row["raw"]["Player_ID"] != riders[car]["rider_id"]:
            raise ValueError("rate_rider_identity_mismatch")
        rates = []
        for column, target in RATE_MAP.items():
            if target in feature:
                raise ValueError("refusing_to_overwrite_rate_feature")
            cell = _cell(column, row["raw"].get(column))
            if cell["state"] == "invalid":
                raise ValueError("invalid_rate")
            rates.append(cell["value"])
            feature[target] = cell["value"]
        known = [r for r in rates if r is not None]
        if known != sorted(known):
            raise ValueError("inconsistent_rate_order")
    result["rate_feature_review"] = copy.deepcopy(review)
    result["training_approved"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output_already_exists")
    result = collect(json.loads(args.manifest.read_text(encoding="utf-8")), args.source_root)
    result["review_records"] = review_records(result)
    data = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

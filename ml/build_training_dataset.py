from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from dataset import build_rows


def _records_from_json(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        for item in data["records"]:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict) and isinstance(data.get("history_record"), dict):
        yield data["history_record"]
    elif isinstance(data, dict) and "race_id" in data:
        yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item


def load_records(paths: list[Path]) -> list[dict[str, Any]]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        elif path.suffix.lower() == ".json":
            files.append(path)
    records: list[dict[str, Any]] = []
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to read {file}: {exc}") from exc
        records.extend(_records_from_json(data))
    return records


def write_csv(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe rider-level training data from keirin history JSON."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="History JSON files or directories")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--summary", type=Path, help="Optional JSON summary path")
    args = parser.parse_args()

    records = load_records(args.inputs)
    rows, summary = build_rows(records)
    write_csv(rows, args.output)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    if summary["eligible_unique_races"] == 0:
        print("No supervised-training-eligible prospective races were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

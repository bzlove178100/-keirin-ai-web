import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ml.historical_details import collect, review_records, attach_reviewed_rates
from ml.historical_training import digest, prepare
from test_historical_entrants import fixture


class DetailedIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        candidates, entrants = fixture()
        self.tables = {**copy.deepcopy(candidates["records"][0]["raw"]), "entrants": entrants}
        for row in entrants:
            row.update(Win_Rate="10", Top2_Rate="20", Top3_Rate="30", Gear_Ratio="3.92",
                       Age="30", New_Provider_Field="keep this verbatim")
        self.manifest = {"schema_version": "historical-detail-manifest-v1", "files": []}
        for role, rows in self.tables.items():
            self.add_file(role, rows, role + ".csv")

    def add_file(self, role, rows, name):
        path = self.root / name
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        self.manifest["files"].append({"provider": "keirindb", "role": role, "path": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_url": "https://example.test/synthetic-source", "observed_at": "2026-10-08T06:00:00Z",
            "observation_evidence": "synthetic-only"})

    def test_full_columns_missing_states_and_training_boundary(self):
        detail = collect(self.manifest, self.root)
        self.assertEqual(detail["summary"]["race_observations"], 1)
        self.assertEqual(detail["summary"]["races_with_all_four_tables"], 1)
        entry = detail["records"][0]["tables"]["entrants"][0]
        self.assertEqual(entry["raw"]["New_Provider_Field"], "keep this verbatim")
        self.assertEqual(entry["cells"]["H"], {"state": "blank", "value": None})
        self.assertEqual(entry["cells"]["Term"], {"state": "absent", "value": None})
        self.assertEqual(entry["cells"]["S"], {"state": "value", "value": 0})
        self.assertEqual(detail["field_coverage"]["entrants.Gear_Ratio"], {"value": 7})
        self.assertEqual(entry["origins"][0]["observed_at"], "2026-10-08T06:00:00Z")
        self.assertIsNone(detail["records"][0]["feature_as_of"])
        converted = review_records(detail)
        self.assertEqual(len(converted["records"]), 1)
        self.assertNotIn("recent_win_rate", converted["records"][0]["pre_race_features"][0])
        plan = prepare(converted["records"], [], "2020-02-01T00:00:00Z", "2020-03-01T00:00:00Z")
        self.assertEqual(sum(plan["partition_counts"].values()), 0)
        self.assertEqual(detail, collect(self.manifest, self.root))

    def test_duplicate_files_rows_and_conflicts(self):
        self.add_file("entrants", self.tables["entrants"] * 2, "duplicates.csv")
        detail = collect(self.manifest, self.root)
        self.assertEqual(detail["summary"]["duplicate_rows"], 14)
        self.assertEqual(detail["summary"]["rows_by_role"]["entrants"], 7)
        self.assertEqual(len(review_records(detail)["records"]), 1)
        changed = {**self.tables["entrants"][0], "Gear_Ratio": "3.93"}
        self.add_file("entrants", [changed], "conflict.csv")
        detail = collect(self.manifest, self.root)
        self.assertEqual(detail["summary"]["conflicting_keys"], 1)
        self.assertEqual(review_records(detail)["records"], [])
        self.assertEqual(len(detail["records"][0]["tables"]["entrants"]), 8)
        self.manifest["files"].append(copy.deepcopy(self.manifest["files"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_source_file"):
            collect(self.manifest, self.root)

    def test_missing_table_and_withdrawn_car_are_not_reconstructed(self):
        self.manifest["files"] = [s for s in self.manifest["files"] if s["role"] != "entrants"]
        detail = collect(self.manifest, self.root)
        self.assertEqual(detail["records"][0]["missing_roles"], ["entrants"])
        self.assertEqual(review_records(detail)["records"], [])
        rows = copy.deepcopy(self.tables["entrants"])
        rows[-1].update(Car="", Status="欠場")
        self.add_file("entrants", rows, "withdrawn.csv")
        detail = collect(self.manifest, self.root)
        self.assertIn("car_missing_or_invalid", detail["records"][0]["quarantine_reasons"])
        self.assertEqual(review_records(detail)["records"], [])

    def test_invalid_numeric_kept_raw_and_quarantined(self):
        for value in ("NaN", "inf", "101", "-1", "1,000"):
            with self.subTest(value=value):
                self.manifest["files"] = [s for s in self.manifest["files"] if s["role"] != "entrants"]
                rows = copy.deepcopy(self.tables["entrants"])
                rows[0]["Win_Rate"] = value
                self.add_file("entrants", rows, "bad-rate.csv")
                detail = collect(self.manifest, self.root)
                self.assertEqual(detail["field_coverage"]["entrants.Win_Rate"]["invalid"], 1)
                self.assertEqual(review_records(detail)["records"], [])
                self.assertTrue(any(r["raw"]["Win_Rate"] == value for r in detail["records"][0]["tables"]["entrants"]))

    def test_source_change_header_width_and_path_escape_stop(self):
        spec = self.manifest["files"][0]
        path = self.root / spec["path"]
        path.write_text("Race_ID,Race_ID\na,b\n")
        with self.assertRaisesRegex(ValueError, "digest_mismatch"): collect(self.manifest, self.root)
        spec["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "header"): collect(self.manifest, self.root)
        path.write_text("Race_ID,Date\na\n")
        spec["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "width"): collect(self.manifest, self.root)
        spec["path"] = "../outside.csv"
        with self.assertRaisesRegex(ValueError, "outside_root"): collect(self.manifest, self.root)

    def test_bad_race_id_is_preserved_separately(self):
        self.add_file("info", [{**self.tables["info"][0], "Race_ID": ""}], "bad-id.csv")
        detail = collect(self.manifest, self.root)
        self.assertEqual(len(detail["unassigned_rows"]), 1)
        self.assertEqual(detail["summary"]["race_observations"], 1)

    def test_detail_tampering_stops_bridge(self):
        detail = collect(self.manifest, self.root)
        detail["records"][0]["tables"]["entrants"][0]["raw"]["Points"] = "999"
        with self.assertRaisesRegex(ValueError, "changed"): review_records(detail)

    def rate_fixture(self):
        detail = collect(self.manifest, self.root)["records"][0]
        record = review_records(collect(self.manifest, self.root))["records"][0]
        record.update(feature_as_of="2020-01-01T09:00:00+09:00",
                      listed_scheduled_start_jst="2020-01-01T10:00:00+09:00",
                      result_available_at="2020-01-01T10:10:00+09:00",
                      pre_race_state_verified=True, training_use_status="confirmed")
        review = {"record_sha256": digest(record), "detail_sha256": digest(detail),
                  "reviewer": "synthetic", "rate_definition_evidence": "synthetic", "feature_time_evidence": "synthetic",
                  "denominator": "started_races", "unit": "percent",
                  "window_start": "2019-09-01T00:00:00+09:00", "window_end": "2020-01-01T00:00:00+09:00"}
        return record, detail, review

    def test_reviewed_rates_reach_existing_training_only_with_new_final_hash(self):
        record, detail, review = self.rate_fixture()
        original = copy.deepcopy(record)
        extended = attach_reviewed_rates(record, detail, review)
        self.assertEqual(record, original)
        self.assertEqual(extended["pre_race_features"][0]["recent_top3_rate"], 30)
        self.assertFalse(extended["training_approved"])
        final_review = {"race_id": record["race_id"], "record_sha256": digest(extended),
                        **{k: "synthetic-only" for k in ("reviewer", "source_use_evidence", "feature_time_evidence", "result_time_evidence")}}
        plan = prepare([extended], [final_review], "2020-02-01T00:00:00Z", "2020-03-01T00:00:00Z")
        self.assertEqual(plan["partition_counts"]["train"], 1)
        self.assertEqual(plan["partitions"]["train"][0]["rows"][0]["recent_top3_rate"], 30)
        final_review["record_sha256"] = digest(original)
        plan = prepare([extended], [final_review], "2020-02-01T00:00:00Z", "2020-03-01T00:00:00Z")
        self.assertEqual(plan["partition_counts"]["train"], 0)

    def test_rates_reject_future_window_missing_definition_and_wrong_identity(self):
        for change in ({"window_end": "2020-01-01T10:00:00+09:00"}, {"denominator": "unknown"},
                       {"rate_definition_evidence": ""}, {"record_sha256": "wrong"}):
            record, detail, review = self.rate_fixture()
            with self.assertRaises(ValueError): attach_reviewed_rates(record, detail, {**review, **change})
        record, detail, review = self.rate_fixture()
        detail["tables"]["entrants"][0]["raw"]["Player_ID"] = "1"
        review["detail_sha256"] = digest(detail)
        with self.assertRaisesRegex(ValueError, "identity_mismatch"): attach_reviewed_rates(record, detail, review)

    def test_three_to_nine_rider_intake(self):
        for count in (3, 5, 6, 7, 9):
            candidates, entrants = fixture(count)
            tables = {**candidates["records"][0]["raw"], "entrants": entrants}
            self.manifest["files"] = []
            for role, rows in tables.items(): self.add_file(role, rows, role + ".csv")
            result = review_records(collect(self.manifest, self.root))
            self.assertEqual(result["records"][0]["rider_count"], count)

    def test_inconsistent_and_preexisting_rates_are_not_silently_accepted(self):
        record, detail, review = self.rate_fixture()
        detail["tables"]["entrants"][0]["raw"]["Win_Rate"] = "90"
        review["detail_sha256"] = digest(detail)
        with self.assertRaisesRegex(ValueError, "rate_order"):
            attach_reviewed_rates(record, detail, review)
        record, detail, review = self.rate_fixture()
        record["pre_race_features"][0]["recent_win_rate"] = 0
        review["record_sha256"] = digest(record)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            attach_reviewed_rates(record, detail, review)

    def test_cli_private_output_never_overwrites(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        output = self.root / "details.json"
        args = [sys.executable, "-m", "ml.historical_details", str(manifest), "--source-root", str(self.root), "--output", str(output)]
        subprocess.run(args, check=True, capture_output=True)
        original = output.read_bytes()
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

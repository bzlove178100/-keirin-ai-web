import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ml.historical_entrants import enrich
from ml.historical_records import convert
from ml.historical_training import digest, prepare
from test_historical_entrants import fixture
from test_historical_payouts import fixture as payout_fixture
from ml.historical_payouts import normalize


class HistoricalRecordTests(unittest.TestCase):
    def test_three_to_nine_riders_preserve_values_identity_and_missing_times_without_approval(self):
        for count in range(3, 10):
            candidates, entrants = fixture(count)
            report = enrich(candidates, entrants)
            before = copy.deepcopy(report)
            result = convert(report)
            record = result["records"][0]
            self.assertEqual(record["rider_count"], count)
            self.assertEqual(record["riders"], report["records"][0]["participants"])
            self.assertIsNone(record["pre_race_features"][0]["H"])
            self.assertIsNone(record["feature_as_of"])
            self.assertIsNone(record["listed_scheduled_start_jst"])
            self.assertIsNone(record["result_available_at"])
            self.assertEqual(result["record_hashes"][record["race_id"]], digest(record))
            self.assertEqual(record["sources"][0]["candidate_sha256"], report["records"][0]["candidate_sha256"])
            self.assertEqual(report, before)
            plan = prepare(result["records"], [], "2024-02-01T00:00:00+09:00", "2024-03-01T00:00:00+09:00")
            self.assertEqual(plan["partition_counts"], {"train": 0, "validation": 0, "test": 0})
            self.assertIn("training_use_unconfirmed", plan["excluded"][0]["reasons"])

    def test_upstream_quarantine_and_orphans_are_not_silently_accepted(self):
        candidates, entrants = fixture()
        entrants[0]["Car"] = ""
        report = enrich(candidates, entrants)
        result = convert(report)
        self.assertEqual(result["records"], [])
        self.assertEqual(result["summary"]["quarantined_races"], 1)
        self.assertIn("entrant_car_missing_or_invalid", result["quarantined_records"][0]["upstream_reasons"])
        candidates, entrants = fixture()
        entrants[0]["Race_ID"] = "orphan"
        report = enrich(candidates, entrants)
        self.assertEqual(convert(report)["orphan_entrant_races"], report["orphan_entrant_races"])

    def test_changed_hash_and_rehashed_derived_values_are_rejected(self):
        for rehash in (False, True):
            candidates, entrants = fixture()
            report = enrich(candidates, entrants)
            row = report["records"][0]
            row["pre_race_features"][0]["race_score"] = 100
            if rehash: row["candidate_sha256"] = digest({k:v for k,v in row.items() if k != "candidate_sha256"})
            with self.assertRaisesRegex(ValueError, "mismatch"): convert(report)

    def test_old_candidate_review_does_not_match_converted_record(self):
        candidates, entrants = fixture()
        report = enrich(candidates, entrants)
        converted = convert(report)["records"][0]
        old = report["records"][0]["candidate_sha256"]
        self.assertNotEqual(old, digest(converted))
        plan = prepare([converted], [{"race_id": converted["race_id"], "record_sha256": old}],
                       "2024-02-01T00:00:00Z", "2024-03-01T00:00:00Z")
        self.assertIn("review_missing_or_record_changed", plan["excluded"][0]["reasons"])

    def test_synthetic_final_review_can_use_the_existing_training_contract(self):
        candidates, entrants = fixture()
        record = convert(enrich(candidates, entrants))["records"][0]
        # Explicit synthetic attestations only, never applied to private data.
        record.update(training_use_status="confirmed", pre_race_state_verified=True,
                      feature_as_of="2024-01-01T09:00:00+09:00",
                      listed_scheduled_start_jst="2024-01-01T10:00:00+09:00",
                      result_available_at="2024-01-01T10:10:00+09:00")
        review = {"race_id": record["race_id"], "record_sha256": digest(record),
                  **{k: "synthetic-fixture" for k in ("reviewer", "source_use_evidence",
                                                     "feature_time_evidence", "result_time_evidence")}}
        plan = prepare([record], [review], "2024-02-01T00:00:00Z", "2024-03-01T00:00:00Z")
        self.assertEqual(plan["partition_counts"], {"train": 1, "validation": 0, "test": 0})
        self.assertEqual(plan["excluded"], [])
        self.assertEqual(sum(r["target_first"] for r in plan["partitions"]["train"][0]["rows"]), 1)

    def test_dead_heat_and_full_refund_stay_outside_single_label_training(self):
        for refund in (False, True):
            info, results, payouts = payout_fixture()
            _, entrants = fixture()
            for row in results: row["Player_Name"] = "Synthetic " + row["Player_ID"]
            if refund:
                for row in results[2:]: row.update(Rank="", Status="落車")
                payouts[1].update(Outcome="全返還", Payout="全返還")
            else:
                results[2]["Rank"] = "2"
                payouts[1].update(Outcome="1-2-3")
                payouts.append({**payouts[1], "Outcome": "1-3-2"})
                payouts[0].update(Outcome="1-2")
                payouts.append({**payouts[0], "Outcome": "1-3"})
            report = enrich(normalize(info, results, payouts), entrants)
            converted = convert(report)["records"][0]
            self.assertEqual(converted["trifecta_settlement"]["status"], "full_refund" if refund else "dead_heat")
            self.assertEqual(len(converted["trifecta_outcomes"]), 0 if refund else 2)
            plan = prepare([converted], [], "2024-02-01T00:00:00Z", "2024-03-01T00:00:00Z")
            self.assertEqual(sum(plan["partition_counts"].values()), 0)

    def test_withdrawal_status_is_retained_without_inventing_a_smaller_prerace_roster(self):
        info, results, payouts = payout_fixture()
        _, entrants = fixture()
        for row in results: row["Player_Name"] = "Synthetic " + row["Player_ID"]
        results[-1].update(Rank="", Status="欠場")
        entrants[-1]["Status"] = "欠場"
        record = convert(enrich(normalize(info, results, payouts), entrants))["records"][0]
        self.assertEqual(record["rider_count"], 7)
        self.assertEqual(record["actual_starters"], 6)
        self.assertEqual(record["riders"][-1]["status"], "DNS")
        self.assertFalse(record["pre_race_state_verified"])

    def test_duplicate_ids_and_wrong_report_schema_fail(self):
        candidates, entrants = fixture()
        report = enrich(candidates, entrants)
        report["records"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"): convert(report)
        with self.assertRaisesRegex(ValueError, "report_required"): convert(candidates)

    def test_cli_refuses_to_overwrite_private_output(self):
        candidates, entrants = fixture()
        with tempfile.TemporaryDirectory() as root:
            source, out = Path(root)/"input.json", Path(root)/"output.json"
            source.write_text(json.dumps(enrich(candidates, entrants)))
            command = [sys.executable, "-m", "ml.historical_records", str(source), "--output", str(out)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr.decode())
            original = out.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(out.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

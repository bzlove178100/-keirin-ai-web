import copy
import csv
import tempfile
import unittest
from pathlib import Path

from ml.historical_entrants import enrich, load_entrants
from ml.historical_payouts import normalize
from ml.historical_training import digest
from test_historical_payouts import fixture as payout_fixture


def fixture(count=7):
    info, results, payoffs = payout_fixture(count)
    for row in results:
        row["Player_Name"] = "Synthetic " + row["Player_ID"]
    entrants = [{"Race_ID": row["Race_ID"], "Car": row["Car"],
                 "Player_ID": row["Player_ID"], "Player_Name": row["Player_Name"],
                 "Status": "", "Style": "追", "Points": "82.75", "S": "0", "H": "", "B": "2",
                 "Win_Rate": "99.99", "Out_Count": "12"} for row in results]
    return normalize(info, results, payoffs), entrants


class HistoricalEntrantTests(unittest.TestCase):
    def test_join_retains_provenance_missing_values_and_does_not_approve(self):
        for count in (3, 7, 9):
            candidates, entrants = fixture(count)
            before = copy.deepcopy((candidates, entrants))
            report = enrich(candidates, entrants[::-1])
            row = report["records"][0]
            self.assertEqual(row["entrant_join_status"], "matched_unverified_features")
            self.assertEqual(row["pre_race_features"][0], {"car_number": 1, "style": "追", "race_score": 82.75, "S": 0, "H": None, "B": 2})
            self.assertEqual(row["raw"], candidates["records"][0]["raw"])
            self.assertEqual(row["parent_candidate_sha256"], candidates["records"][0]["candidate_sha256"])
            self.assertEqual(row["candidate_sha256"], digest({k: v for k, v in row.items() if k != "candidate_sha256"}))
            self.assertEqual(row["raw_entrants_sha256"], digest(entrants[::-1]))
            self.assertEqual((candidates, entrants), before)
            self.assertIsNone(row["feature_as_of"])
            self.assertIsNone(row["result_available_at"])
            self.assertFalse(row["pre_race_state_verified"])
            self.assertFalse(row["training_approved"])
            self.assertEqual(report["summary"]["training_runs"], 0)

    def test_wrong_race_is_not_joined_by_player_or_car(self):
        candidates, entrants = fixture()
        for row in entrants: row["Race_ID"] = "different_race"
        report = enrich(candidates, entrants)
        self.assertEqual(report["records"][0]["entrant_join_reasons"], ["entrant_rows_missing"])
        self.assertEqual(report["orphan_entrant_races"][0]["raw_entrants"], entrants)

    def test_identity_name_and_car_conflicts_are_quarantined(self):
        for field, value in (("Player_ID", "1"), ("Player_Name", "different"), ("Car", "8"),
                             ("Player_ID", ""), ("Style", "unknown"), ("Status", "欠場")):
            with self.subTest(field=field):
                candidates, entrants = fixture()
                entrants[0][field] = value
                row = enrich(candidates, entrants)["records"][0]
                self.assertEqual(row["entrant_join_status"], "quarantined")
                self.assertEqual(row["pre_race_features"], [])

    def test_missing_withdrawn_car_is_never_inferred_from_results(self):
        info, results, payoffs = payout_fixture()
        for row in results: row["Player_Name"] = "Synthetic " + row["Player_ID"]
        results[-1].update(Rank="", Status="欠場")
        candidates = normalize(info, results, payoffs)
        _, entrants = fixture()
        entrants[-1].update(Car="", Status="欠場")
        report = enrich(candidates, entrants)
        self.assertEqual(report["records"][0]["entrant_join_reasons"], ["entrant_car_missing_or_invalid"])
        self.assertEqual(report["records"][0]["raw_entrants"][-1]["Car"], "")

    def test_numeric_inputs_are_not_silently_coerced(self):
        for field, value in (("Points", "NaN"), ("Points", "inf"), ("Points", "-1"),
                             ("S", "1.5"), ("H", "unknown"), ("B", "1,000")):
            candidates, entrants = fixture()
            entrants[0][field] = value
            row = enrich(candidates, entrants)["records"][0]
            self.assertIn("invalid_entrant_numeric:" + field, row["entrant_join_reasons"])
            self.assertEqual(row["pre_race_features"], [])

    def test_duplicates_and_incomplete_rosters(self):
        candidates, entrants = fixture()
        report = enrich(candidates, entrants * 2)
        self.assertEqual(report["summary"]["matched_rider_rows"], 7)
        self.assertEqual(report["summary"]["identical_duplicate_rows_ignored"], 7)
        for rows in (entrants[:-1], entrants + [{**entrants[0], "Points": "90"}],
                     entrants[:-1] + [{**entrants[0], "Points": "90"}]):
            self.assertEqual(enrich(candidates, rows)["records"][0]["entrant_join_status"], "quarantined")

    def test_missing_year_remains_missing_not_filled_from_other_year(self):
        candidates, _ = fixture()
        report = enrich(candidates, [])
        self.assertEqual(report["summary"]["matched_rider_rows"], 0)
        self.assertEqual(report["summary"]["exclusion_reason_counts"], {"entrant_rows_missing": 1})

    def test_modified_candidate_and_existing_features_are_not_overwritten(self):
        candidates, entrants = fixture()
        candidates["records"][0]["raw"]["info"][0]["Venue"] = "changed"
        with self.assertRaisesRegex(ValueError, "digest_mismatch"): enrich(candidates, entrants)
        candidates, entrants = fixture()
        row = candidates["records"][0]
        row["pre_race_features"] = [{"car_number": 1}]
        row["candidate_sha256"] = digest({k:v for k,v in row.items() if k != "candidate_sha256"})
        with self.assertRaisesRegex(ValueError, "overwrite"): enrich(candidates, entrants)

    def test_unsettled_payout_is_not_made_usable_by_entrant_join(self):
        info, results, payoffs = payout_fixture()
        payoffs[1]["Outcome"] = "unknown"
        _, entrants = fixture()
        row = enrich(normalize(info, results, payoffs), entrants)["records"][0]
        self.assertEqual(row["entrant_join_reasons"], ["payout_candidate_not_normalized"])

    def test_csv_validation_and_original_hash(self):
        _, entrants = fixture()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "entrants.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(entrants[0]))
                writer.writeheader(); writer.writerows(entrants); writer.writerow({})
            before = path.read_bytes()
            rows, receipt = load_entrants(path)
            self.assertEqual(rows, entrants)
            self.assertEqual(receipt["blank_rows_ignored"], 1)
            self.assertEqual(before, path.read_bytes())
            path.write_text("Player_ID,Player_Name\n90001,Synthetic\n")
            with self.assertRaisesRegex(ValueError, "header"): load_entrants(path)
            path.write_bytes(before + b"too,few,columns\n")
            with self.assertRaisesRegex(ValueError, "width"): load_entrants(path)


if __name__ == "__main__":
    unittest.main()

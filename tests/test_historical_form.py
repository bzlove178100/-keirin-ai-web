import copy
import unittest

from ml.historical_form import build


def target():
    return {"race_id": "target", "feature_as_of": "2020-02-01T10:00:00+09:00",
            "listed_scheduled_start_jst": "2020-02-01T10:10:00+09:00",
            "identity_evidence": "synthetic roster", "entry_time_evidence": "synthetic archive",
            "riders": [{"car_number": n, "rider_id": f"synthetic:rider-{n}"} for n in range(1, 8)]}


def past(key="past", start="2020-01-01T10:00:00+09:00", available="2020-01-01T11:00:00+09:00"):
    return {"race_id": key, "race_status": "completed", "race_start_at": start,
            "result_available_at": available,
            **{k: "synthetic evidence" for k in ("identity_evidence", "result_time_evidence", "source_use_evidence")},
            "participants": [{"car_number": n, "rider_id": f"synthetic:rider-{n}",
                              "status": "FINISHED", "finish_rank": n} for n in range(1, 8)]}


class HistoricalFormTests(unittest.TestCase):
    def test_future_result_and_self_do_not_change_features(self):
        control = build(target(), [past()])
        late = past("late", available="2020-02-01T10:00:00+09:00")
        future = past("future", "2020-02-02T10:00:00+09:00", "2020-02-02T11:00:00+09:00")
        result = build(target(), [past(), late, future, past("target")])
        self.assertEqual(result["riders"], control["riders"])
        self.assertEqual(len(result["excluded_history"]), 3)
        self.assertFalse(result["training_approved"])

    def test_car_number_changes_use_stable_identity(self):
        r = past()
        r["participants"][0]["car_number"], r["participants"][1]["car_number"] = 2, 1
        result = build(target(), [r])
        self.assertEqual(result["riders"][0]["features"]["recent_win_rate"], 100)
        self.assertEqual(result["riders"][1]["features"]["recent_win_rate"], 0)

    def test_no_identity_guessing_from_car_or_name(self):
        r = past()
        r["participants"][0].pop("rider_id")
        result = build(target(), [r])
        self.assertEqual(result["provenance"], [])
        self.assertIsNone(result["riders"][0]["features"]["recent_win_rate"])

    def test_no_history_is_missing_not_zero(self):
        result = build(target(), [])
        self.assertEqual(result["riders"][0]["starts"], 0)
        self.assertTrue(all(v is None for v in result["riders"][0]["features"].values()))

    def test_dnf_dsq_count_as_starts_but_dns_does_not(self):
        history = [past()]
        for i, status in enumerate(("DNF", "DSQ", "DNS")):
            r = past(str(i))
            r["participants"][0].update(status=status, finish_rank=None)
            for p in r["participants"][1:]:
                p["finish_rank"] -= 1
            history.append(r)
        row = build(target(), history)["riders"][0]
        self.assertEqual(row["starts"], 3)
        self.assertEqual(row["classified_finishes"], 1)
        self.assertAlmostEqual(row["features"]["recent_win_rate"], 100 / 3)
        self.assertEqual(row["features"]["recent_avg_finish"], 1)

    def test_ties_keep_competition_ranks(self):
        r = past()
        r["participants"][1]["finish_rank"] = 1
        rows = build(target(), [r])["riders"]
        self.assertEqual([x["features"]["recent_win_rate"] for x in rows[:3]], [100, 100, 0])

    def test_duplicate_and_conflict_do_not_inflate_sample(self):
        a, b = past(), past()
        result = build(target(), [a, b])
        self.assertEqual(result["identical_duplicates"], 1)
        self.assertEqual(result["riders"][0]["starts"], 1)
        b["participants"][0]["finish_rank"] = 2
        self.assertEqual(build(target(), [a, b])["riders"][0]["starts"], 0)

    def test_window_is_by_event_time_not_collection_time(self):
        result = build(target(), [past()], window_days=10)
        self.assertEqual(result["riders"][0]["starts"], 0)

    def test_no_evidence_or_naive_times_rejected(self):
        for mutate in (lambda r: r.pop("result_time_evidence"),
                       lambda r: r.update(result_available_at="2020-01-01T11:00:00"),
                       lambda r: r.update(result_available_at="2019-12-01T11:00:00+09:00"),
                       lambda r: r.update(race_status="cancelled")):
            r = past()
            mutate(r)
            self.assertEqual(build(target(), [r])["provenance"], [])

    def test_target_must_have_pre_start_cutoff_and_identity(self):
        for mutate in (lambda r: r.pop("identity_evidence"),
                       lambda r: r.update(feature_as_of=r["listed_scheduled_start_jst"])):
            r = target()
            mutate(r)
            with self.assertRaises(ValueError):
                build(r, [])

    def test_provenance_hash_changes_with_result_input(self):
        a, b = past(), past()
        b["result_available_at"] = "2020-01-01T12:00:00+09:00"
        self.assertNotEqual(build(target(), [a])["provenance"][0]["record_sha256"],
                            build(target(), [b])["provenance"][0]["record_sha256"])

    def test_malformed_rank_or_duplicate_identity_quarantines_race(self):
        for mutate in (lambda r: r["participants"][0].update(finish_rank=True),
                       lambda r: r["participants"][0].update(finish_rank=2),
                       lambda r: r["participants"][0].update(rider_id="synthetic:rider-2")):
            r = past()
            mutate(r)
            self.assertEqual(build(target(), [r])["provenance"], [])


if __name__ == "__main__":
    unittest.main()

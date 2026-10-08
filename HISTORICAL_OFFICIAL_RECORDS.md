# Join official captures for historical review

`ml.historical_official_records` joins saved, pre-start race cards with saved
official result pages. It replays the existing strict HTML importer for both
captures, verifies registration IDs and normalized names, and enforces chronology
against all start times recorded in both captures. It never fetches or backdates.

Run with a private manifest and a new output path outside this public repository:

```sh
python -m ml.historical_official_records /private/pairs.json \
  --output /private/review-records.json
```

The manifest has a `pairs` array. Each entry has `race_date`, `venue_code`,
`race_number`, `pre_html`, `pre_receipt`, `result_html`, and `result_receipt`.
Paths are relative to the manifest directory unless absolute. Retain the original
bytes and receipts; rejected pairs retain their hashes and receipts for diagnosis.
Duplicate race identities fail the batch. An invalid capture pair is quarantined
without changing valid pairs. Output creation refuses replacement.

The output uses `historical-review-records-v1`, including final record hashes,
and can be passed directly to `agent_core.historical_preparation`. This eliminates
manual reconstruction between source capture and the shared preparation runner.
It creates neither training approval nor a prospective prediction snapshot.

Only observed style and score are mapped. S/H/B and rate statistics remain in
the retained raw blocks until their definitions and windows are reviewed. Both
complete observations are retained, including full result classifications and
payouts. Feature time comes from pre-capture completion, not result retrieval.

A withdrawal explicitly present before the start and confirmed afterward is
excluded from the candidate population while remaining in the original roster.
A result-only withdrawal blocks conversion; it cannot silently redefine what
was known before the race. Known retirements remain starters without invented
finish positions. Unknown statuses, conflicting identities and noncontiguous
finish orders require review. Any tied rank is excluded from this single-label
bridge; raw results and all payouts stay available for a future multilabel path.

Privately applied on 2026-10-08: the bounded venue capture now covers all 12
detailed results and separately checked ordered payouts. Four already-saved
pre-race cards produced three unapproved review records (20 active rider rows);
one first-place tie is quarantined. The shared preparation runner accepted the
report and excluded all unreviewed records. This is not training, continuous
collection, source-use clearance, or completion of general-agent runtime work.

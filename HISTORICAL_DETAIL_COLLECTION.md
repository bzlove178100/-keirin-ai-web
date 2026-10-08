# Detailed historical intake

This optional offline path runs alongside the existing agent/note work. It
does not replace existing preparation, change the production feature contract,
fetch a site, write the application database, or enable a scheduled worker.
Current support is KeirinDB CSVs; other providers need their own identity and
schema mappings. It is not an all-site scraper or a complete-data claim.

## What is collected from supplied files

| Table | Known columns | Handling |
| --- | ---: | --- |
| Race information | 13 | Date, venue, category, roster size, observed weather/wind and status |
| Entrants | 27 | Identity, car/frame, score, style, S/H/B, decision and finish counts, rates, gear, grade, age, term, prefecture |
| Results | 10 | Identity, placing/status, gap, lap time, decision and S/B |
| Payoffs | 5 | Bet type, combination, amount and popularity |

Every original column and row is retained, including unexpected new columns.
The 55 figure is the sum across four schemas, including repeated identity
columns, not 55 distinct model features. Known numeric fields are parsed with
finite/range checks. Raw text, empty cells, absent columns and invalid cells are
distinguished. A blank status may mean an ordinary starter/finisher; blank
counts are not universally missing-data counts. Outcome/date repairs remain
the responsibility of the existing strict payout normalizer.

Each row retains file SHA-256, source URL, exact CSV end-line and observation
evidence. An unknown acquisition timestamp stays null. Download time is never
used as historical feature availability. Exact duplicates retain all origins;
conflicting logical keys remain visible and quarantine the whole race. Nothing
is overwritten, inferred from later rider masters, or merged by rider name.

## Private execution

Create a manifest outside the public repository:

```json
{
  "schema_version": "historical-detail-manifest-v1",
  "files": [{
    "provider": "keirindb",
    "role": "entrants",
    "path": "entrants.csv",
    "sha256": "<exact input byte hash>",
    "source_url": "https://example.test/original-source",
    "observed_at": null,
    "observation_evidence": "<retained acquisition receipt; unknown exact times stay null>"
  }]
}
```

Roles are `info`, `entrants`, `results`, and `payoffs`. Relative files must
resolve inside `--source-root`; no URL is fetched. Multiple year files may
share a role. Input hashes must match before parsing. Output must be new.

```bash
python -m ml.historical_details /private/detail_manifest.json \
  --source-root /private/inputs --output /private/detail_intake.json
```

The output includes full detail records, column coverage, conflicts, missing
tables, and an acquisition backlog. It also contains `review_records`, produced
through the existing payout/entrant/review normalizers. This can be passed to
existing historical preparation as a JSON object containing `records`.
Previously approved hashes cannot be carried over to changed records.

Lineups, comments, timestamped odds, bank geometry, pre-race weather, video and
training/equipment changes are explicitly unprovided in these four CSV schemas.
These are backlog categories, not implemented source connectors. The inventory
is versioned and expandable; it does not assert that these categories exhaust
every possible useful detail. A present table does not establish completeness,
correctness, pre-race availability or permission for model training.

## Learning boundary

`attach_reviewed_rates(record, detail_record, review)` can add Win_Rate,
Top2_Rate and Top3_Rate to the existing recent-rate feature columns. The caller
must supply the exact two input hashes, reviewer, definition/time references,
a confirmed started-races denominator and percent unit, and a window ending
no later than feature availability. Roster identity and rate ordering must
match. Existing rate features are not overwritten. This is an operator
attestation and does not independently verify a provider's definition.

It does not label unknown archive rates as recent form automatically. The
result receives a new hash and still needs the existing final source/time
review, chronology checks, sufficient continuous history and frozen evaluation
partitions before training. Source-use and timestamp evidence are not created.
Other detail columns remain preserved observations, not trained features.
There is no current real-data rate review or autonomous training worker.

## Scoped real-data check — 2026-10-08

The existing 11 sample files produced 301 race observations and 6,451 unique
rows: 301 information, 1,408 entrant, 2,028 result and 2,714 payoff rows.
No conflicting keys were found. All four tables are present for 211 races;
three of those have blank entrant car numbers and remain quarantined. The
other 90 have no entrant table. Strict conversion retains the same 208 review
records, with 90 upstream exclusions plus three detail exclusions. All 1,408
supplied H cells are blank; the 2026 sample also lacks 90 weather/wind values.

This reorganizes already acquired data. New unique races: 0. Cumulative unique
observations remain 317. Eligible training races: 0; real-data training runs: 0.
No new permission, source-time evidence, measured accuracy or return is claimed.
Real matched rosters contain 5/6/7 riders; 3–9 support is synthetic coverage.
Private data/evidence stay outside git. User support actions and original
parallel engineering blockers remain separate, unresolved work.

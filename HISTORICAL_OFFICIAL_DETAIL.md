# Saved official race details

`ml.historical_official_detail` imports already saved KEIRIN.JP race pages. It
executes no page scripts and makes no network requests. A receipt pins the raw
HTML bytes, HTTPS source, request/completion times and successful HTTP status.
The expected date, venue code and race number must match the official header.

```sh
python -m ml.historical_official_detail /private/race.html /private/receipt.json \
  --date 2026-01-02 --venue-code 35 --race-number 1 --mode result \
  --output /private/detail.json
```

Use `--mode pre` for a saved race card. Completion must precede both the original
and revised listed starts. An old page-update label never backdates a later
capture. Output is created exclusively; originals are not changed.

The output retains every field in the `PC0201` header and `PJ0315` card or
`PJ0326` result block, including nested previous results and unknown fields.
Three to nine listed rider rows are supported. Stable registration IDs and car
numbers must reconcile exactly between header and detail. Missing or duplicate
blocks, changed identities and incomplete rosters stop the import.

Results preserve full rider classifications, withdrawals, retirement states,
finish margins, closing times, tactics, weather/wind, all offered payout fields
and refund notes in the raw blocks. A small summary normalizes ordered payouts
and cross-checks untied top-three finishers. For tied competition ranks such as
`1, 1, 3`, both exacta and trifecta combinations must exactly match the ordered
prefixes consistent with every observed rank group. Missing, extra or incorrect
combinations are flagged even when both payout tables agree with each other,
including when the only tie is below third place. Other rank conventions and
insufficient ranked finishers remain raw and require review. Expansion is limited
to the required two/three places (at most 72/504 combinations for nine riders).

This is an internal rank/payout consistency check, not independent confirmation
of the result, source-use approval, payout calculation or a new training label.
Amounts and all original rows are retained unchanged; exceptional payouts stay
raw and flagged. The single-label review bridge still quarantines tied ranks.

## Separately captured official JSON results

`ml.historical_official_json.ingest_json_result` accepts original bytes and
individual receipts for the public page's `JSJ001` header and `JSJ012` result
responses. Both must be successful GETs to the exact HTTPS `/pc/json` endpoint,
with the expected request types and the same nonempty `encp` selection. The
header's selected token and requested date/venue/race must match. Redirect
parameter changes, duplicate query/JSON keys, nonfinite JSON, changed bytes,
unpublished finish/payout flags and pre-start captures are rejected.

The normalizer uses the same roster, status, tie and payout checks as saved HTML.
It retains both complete JSON blocks, the two source hashes and scoped receipt
fields without synthesizing an HTML source. `source_sha256` is explicitly labeled
as a digest of the `source_capture_sha256` map for this format; it is not the
hash of a downloaded HTML page. Observation time is the later completion of the
two captures, a conservative known-by time, not exact publication time. Capture
receipts and matching selection tokens do not authenticate the provider or prove
the separate responses are an atomic snapshot. Keep original bytes/receipts.

`ml.historical_official_records.join_json_result` joins those captures to original
pre-race HTML through the existing review bridge. It grants no source approval,
does not backdate features and still quarantines ties or changed withdrawals.
These functions perform no network requests. A failed HTML route and successful
JSON route establish a scoped fallback, not a claim that the server is repaired.

Listed riders, ranked finishers and confirmed starters are separate counts.
An explicit withdrawal is not an invented last-place finish. Known fall,
accident and mechanical retirements count as starts; other non-finisher states
leave the starter count unknown. A listed finish together with an explicit retirement, or withdrawal
and retirement together, is contradictory: raw fields remain unchanged, the
confirmed starter count is unknown and the review bridge quarantines the capture.
Blank status placeholders do not classify a missing finish; they remain valid
on a ranked row. Unknown nonblank statuses are retained without inventing a
meaning. This is internal consistency checking, not correction of source results.
Roster additions/withdrawals on pre-race cards
require review. Unknown statistics and their time windows are not automatically
mapped into model features. These are unapproved observations, not training
records or prediction snapshots; training and automatic collection stay OFF.

## Access diagnosis

A prior linked result lookup returned HTTP 500 with `EC0500E`, including on a
direct HTTPS POST. A later public top-page navigation and its race-selection
parameters returned valid cards and detailed results without authentication.
The same public race-selection token appeared on both source routes. This
establishes a working retrieval route at the later observation time, not the
server-side cause or permanent repair of the earlier error. A future error
must be recorded with its status/time and investigated under a changed condition,
not retried indefinitely or treated as permission to bypass access controls.

The private evidence stores captures and their source receipts outside git.
It also compares the detailed ordered payouts with the separate venue list
and the rider identities with the unchanged earlier paper. Acquisition, field
mapping, source-use review, final-record review and actual learning remain
separate milestones. Existing shared-agent, note and runtime work is unchanged.

## Disqualified crossing evidence (2026-10-09)

An exact `失格` state with blank awarded rank and a string `inLineJyuni`
within the listed roster size can establish that the rider started and crossed
the line. Keep `finish_position` null and keep retirement false: crossing order
is not an awarded placing. Preserve the original value separately. Missing or
malformed crossing evidence, an awarded rank, withdrawal, or contradictory
retirement/crossing state requires review. This deliberately does not cover all
disqualification variants. Unknown states stay unclassified.

Source grounding: the official glossary describes 失格 as a penalty for race
violations (https://keirin.jp/pc/static/beginner/keirin-glossary/sa-so.html).
The captured official `commonRace.js` renders `inLineJyuni` as 入線順位.
Those facts support this limited intake rule, not a guessed awarded finish or
source-use permission. Ordered payouts must still match awarded top-three
positions; original pre-race population, chronology and review gates remain.

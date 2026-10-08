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
and cross-checks untied top-three finishers. Exceptional payouts remain raw and
are flagged for review. Repeated ranks are retained; this module does not prove
all dead-heat payout combinations or make a single training label from them.

Listed riders, ranked finishers and confirmed starters are separate counts.
An explicit withdrawal is not an invented last-place finish. Known fall,
accident and mechanical retirements count as starts; other non-finisher states
leave the starter count unknown. Roster additions/withdrawals on pre-race cards
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

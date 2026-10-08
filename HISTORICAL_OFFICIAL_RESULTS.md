# Offline official ordered-result reconciliation

`ml.historical_official_results` processes saved Shonan Bank result-list HTML
and an immutable, separately captured pre-race source snapshot. It reduces
manual payout transcription. It has no network, scheduler, application database,
training or production action.

The current adapter covers the first-day result-list layout whose `race_start`
query and row `data-name` match the snapshot date. Other days/layouts need an
explicit extension and fixtures; they are not silently inferred.

```bash
python -m ml.historical_official_results \
  /private/pre_race_source_snapshot.json \
  /private/result_list.html \
  /private/result_list.html.receipt.json \
  --snapshot-sha256 <verified-baseline-file-sha256> \
  --output /private/new_result_reconciliation.json
```

The output must be new. Retain original source bytes, receipt, input hash and
output privately. A receipt includes `url`, `final_url`, HTTP `status`, byte
count, SHA-256, timezone-aware `request_started_at` and `download_completed_at`.
The supplied hashes pin the bytes but do not authenticate an operator's receipt.

The adapter checks the desktop table's headings and race/date selectors. Mobile
copies are excluded from counts; duplicate desktop races, changed headings and
missing race sets fail. Blank cells remain pending. Partial data, unfamiliar
refund/status text, invalid amounts and contradictory exacta/trifecta combinations
remain quarantined with original cell text. Multiple ordered outcomes are kept
as arrays and never collapsed to a single training label.

Reconciliation verifies the original snapshot file and each race record hash,
the venue/race key, all cars in each observed outcome, the saved pre-race time,
scheduled start and result observation time. Only the unchanged pre-race score
is copied into review candidates. It does not infer style, S/H/B, rates, stable
identities, weather or odds. The original source snapshot is not rewritten.

`result_available_at` in a candidate is the conservative time by which the
result was observed on the saved page, not its exact publication time or the
actual finish time. Ordered payout lists do not verify the full finish order,
withdrawals, disqualifications or every dead heat. `dead_heat` stays unknown;
source-use and pre-race-review approval remain unconfirmed. Existing preparation
excludes these unreviewed candidates. No previous approval carries to a changed
record hash and no prediction snapshot is manufactured after the result.

Local verification uses synthetic fixtures only in git. The private real-data
check joined four published race summaries and kept eight blank at capture time.
All four candidates were excluded by existing training preparation, with
train/validation/test counts 0/0/0. The diagnostic partition dates are not an
adopted evaluation plan. All remaining source/review requirements still apply.

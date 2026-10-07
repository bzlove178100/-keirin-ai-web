# Prospective real-race collection protocol

Purpose: collect leakage-resistant real-race histories for paired Phase32 baseline vs LightGBM offline evaluation.

## Parallel collection and training proposal — 2026-10-06

### Historical intake follow-up

The user subsequently requested broad historical collection and improved learning,
including nine-rider races. Do not constrain the collection scope to seven riders.
Historical learning needs its own contract; never set old observations to
`prospective` or fabricate pre-race capture timestamps to pass the current gate.

Initial public-page research examined six source candidates: KEIRIN.JP, WINTICKET,
K-Dreams, Yenjoy, netkeirin, and a third-party GitHub dataset description. Coverage
and access depth differ; this is not six approved/connected feeds. Four factual
sample races were saved privately (three seven-rider races, one nine-rider race;
one dead heat). Two result samples agree across WINTICKET/Yenjoy, but their upstream
independence is unknown. One historical card supplies displayed scores/S/B/style;
the pre-race validity of those displayed statistics remains unverified. No private
records, source text, rider data, models or evaluation artifacts enter this repo.

`python -m ml.historical_audit INPUT --output PRIVATE_OUTPUT` audits curated local
observations for duplicates, conflicting labels, missing rosters and unsupported
dead heats. It preserves rider count and quarantines all history in the intake path.
The dedicated reviewed historical path below is separate. This is intake software, not a scraper
or model trainer. Eight synthetic unit tests pass locally. Four real sample records
were audited: four unique, all quarantined, zero eligible, zero learning runs.

No bulk retrieval or scheduled job has started. Source-specific automated-use
terms, historical feature timing and full data access remain unresolved. The
third-party GitHub data directory returned restricted URL; no alternate access or
circumvention was attempted. Its README is not proof of actual data completeness
or permission. Continue with source qualification and a point-in-time historical
schema rather than declaring model improvement from these sample records.

User intent: accumulate real data and periodically train while the broader agent
and Keirin product are still being developed, reducing avoidable waiting for
prospective evidence. Prioritize this bounded track without discarding the
general-agent goal. This is a prepared plan, not an activated collector.

Confirmed at main c1cfd45a369c34d4102665579cc4e49842042cff:
- `data_source_contract.ts` declares caller_supplied_only and production source disconnected.
- `ml.settle_snapshot`, `ml.collection_status`, dataset building, position-model
  training and chronological evaluation exist; no live collection receipt was found.
- Current prospective training/evaluation requires seven riders and the saved
  full 210-combination baseline. Do not silently include nine-rider or incompatible records.
- Result-only messages cannot reconstruct a genuine pre-race snapshot or become
  prospective evidence. Retain such results separately until a matching prior snapshot exists.

Proposed bounded delivery and acceptance:
1. Confirm a source with permitted automated retrieval, storage and intended
   model-training use, required fields, limits, availability and cost. Candidate
   public pages are not an established licensed feed. Source choice is unresolved.
2. Choose private durable storage and a narrowly permissioned scheduled worker.
   Broader agent completion is not a logical dependency; an independent worker
   still needs its own secret, isolation, recovery, monitoring and cost acceptance.
   Do not reuse the unqualified live-host network path as if safe.
3. Capture stable race/rider IDs, scheduled start, source/provenance, actual
   observation time, pre-race features, available odds and pinned schema/baseline
   before the target cutoff. Preserve raw observations and immutable snapshots.
   Missed/late fetches must be marked missed, never backdated or imputed.
4. After official results are observed, settle only matching snapshots. Detect
   duplicates, conflicts, missing fields, cancelled races and incompatible records;
   quarantine failures, report counts and keep model inputs free of future results.
5. First prove an unattended pre-race-to-settled-history cycle and durable readback,
   including failure/stop/retry behavior. That is the first operational milestone,
   not proof of sufficient data or profitability.
6. With sufficient eligible data and valid chronological partitions, run bounded
   scheduled batch training/evaluation on new data. Deduplicate runs by dataset and
   code version; cap compute, preserve previous models and report skipped/failed runs.
   Frequency and budget remain to be chosen from source cadence and actual workload.
7. Save candidate models and metrics privately. Preserve an untouched future test
   period; do not repeatedly tune against the same holdout. Training success does
   not authorize promotion, production prediction, monetary EV or betting.

The existing five-time evaluator minimum is technical, not a production threshold.
Early collection may shorten the wait for evidence; no duration saved, accuracy
improvement or completion date is estimated from current evidence.

Current blockers: approved source and access method; private storage target;
worker deployment/credentials and budget; collector adapter; end-to-end acceptance.
No external collection, recurring job, model training or production activation
was started by preparing this plan. No recurring ChatGPT reminder substitutes
for a deployed data pipeline.

Initial source review found the KEIRIN.JP policy page:
https://keirin.jp/pc/dfw/portal/guest/policy/index.html
Its publication does not by itself establish permission for this proposed feed.
Do not infer either blanket permission or a blanket legal prohibition on model
training from the general page. Confirm the actual source and intended uses.

## Required order

For each race:

1. Before scheduled start, use only information available at prediction time.
2. Enter the scheduled start in Japan time and explicitly confirm the race has not started.
3. Run owner-only Phase32 dry-run and save the prediction snapshot before scheduled start.
4. Do not edit the saved snapshot after the race.
5. After the official result is available, confirm the trifecta outcome and settlement odds.
6. Record a timezone-aware timestamp for when that confirmed result was observed/recorded. Do not label this as an official publication timestamp unless an authoritative source supplies that exact timestamp.
7. Generate history either through the owner Web/history pipeline or with the local offline builder described below.
8. Confirm the generated record is prospective and supervised-training eligible before adding it to the evaluation dataset.

## Local/offline settlement

`ml.settle_snapshot` provides a network-free fallback for converting a saved prospective snapshot into the same canonical history shape used by offline ML. It performs no database writes and does not enable production prediction or external fetching.

Example:

```bash
python -m ml.settle_snapshot \
  phase32-snapshot-2026-09-24-race-1.json \
  --outcome 3-4-7 \
  --odds 39.3 \
  --result-timestamp 2026-09-24T17:31:54+09:00 \
  --output backtest-history-2026-09-24-race-1.json
```

The result timestamp in this workflow means the time the already-confirmed result was observed/recorded. It is not automatically an official finish time or official publication time.

The builder validates the prospective flag, pre-start confirmation, seven riders, current Phase32 engine version, full 210-combination probability table, category structure and timestamp ordering before it emits a supervised-training-eligible record. Prediction-time partial odds are preserved exactly; unknown odds are not inferred.

## Collection readiness

Use the local readiness command on private history files or a private directory:

```bash
python -m ml.collection_status /path/to/private/histories --require-ready
```

It reports eligible unique races, distinct prediction times, how many additional distinct times remain before the evaluator's five-time technical minimum, and the known trifecta-odds counts. A passing collection threshold only means the chronological evaluator may be able to form partitions; it is not evidence of statistical sufficiency, accuracy, calibration or profitability.

## Chronological minimum

`ml.evaluate_offline` requires at least five distinct eligible prediction timestamps before it can construct train / validation / test partitions. Four or fewer are intentionally blocked.

Five is only a technical minimum, not evidence of statistical sufficiency. Prefer substantially more races before interpreting accuracy, calibration or model superiority.

## Boundary rule

Prediction and result chronology must prevent label leakage:

- training-race results must already be available before the validation prediction boundary;
- validation-race results must already be available before the test prediction boundary;
- records whose labels were not available at a boundary are purged from that partition.

Therefore, do not capture a batch of many races at the same time and assume it creates a valid chronological evaluation. For efficient collection, settle earlier races before using later prediction times as the next evaluation boundary whenever possible.

## Odds policy

Confirmed partial trifecta odds may be retained. Missing odds must never be invented. The Phase32 baseline probability table remains all 210 combinations; prediction-time odds coverage is recorded separately as input quality.

## Safety constraints

Keep these OFF during development collection:

- production prediction
- database writing from development prediction/history flows
- external automatic data fetching
- monetary EV / promotion decisions while probabilities are uncalibrated

Do not commit private snapshots, real histories, model artifacts or evaluation reports to this public repository.

## Reviewed historical training contract — 2026-10-07

`ml.historical_training` does not reuse prospective eligibility or populate a
fictional `prediction_timestamp`. Its private input is the intake records array,
plus a separate reviews array. Each review contains `race_id`, `record_sha256`
(from `ml.historical_training.digest`), `reviewer`, `source_use_evidence`,
`feature_time_evidence`, and `result_time_evidence`. Evidence values reference
actual reviewed documentation; writing arbitrary text is not source verification.
A changed record invalidates its review. Duplicate conflicting races are excluded.

Records require explicit `prospective: false`, `dead_heat: false`, verified
pre-race status, confirmed source-use status, complete seven/nine rider rosters,
and one valid trifecta outcome. Required timezone-aware times are `feature_as_of`,
`listed_scheduled_start_jst`, and `result_available_at`, in that order (features
strictly before start). Result availability is supported by evidence or a
conservative observation timestamp, not a guessed official publication time.
`pre_race_features` must contain one matching row per rider, with car_number,
style and optional race_score/S/H/B numeric fields. Unknown values stay missing.
Archived displayed statistics are never automatically copied into these fields.
No result, final odds, comments or other columns are admitted as model features.

Choose and freeze explicit validation/test boundaries before model selection:

```bash
python -m ml.historical_training PRIVATE_INTAKE PRIVATE_REVIEWS \
  --validation-start VERIFIED_BOUNDARY --test-start VERIFIED_BOUNDARY \
  --output NEW_PRIVATE_PLAN
```

The default writes a plan only. Adding `--train` treats output as a new private
model directory, fits the existing position rankers on train, early-stops on
validation, and reports the held-out test metrics. At least two train races and
one in each later partition are a technical execution minimum only. They are
not sufficient evidence for accuracy, generalization or profitability. Models
are uncalibrated, not deployed, and not prospective comparison evidence. All
remaining shared numeric features are missing in this initial historical path.
Never publish private reviews/data/model files or tune against repeated test results.

Local checks: 19 synthetic unit tests plus one successful synthetic LightGBM
execution (12 races: 8/2/2; seven/nine riders). Four existing real samples were
rejected as expected; zero real training runs. CI wiring added but not yet
qualified. Source access, verified historical features and actual collection
remain unresolved. No autonomous job is running.

## Result-derived form candidates — 2026-10-07

`python -m ml.historical_form PRIVATE_TARGET PRIVATE_RESULT_ARRAY --window-days 120 --output NEW_PRIVATE_CANDIDATES`

This offline builder offers an alternative to using potentially refreshed archive
statistics. It reconstructs custom recent_win_rate / recent_top2_rate /
recent_top3_rate percentages and recent_avg_finish from supplied reviewed results.
It does not claim to reproduce official statistics or a complete career history.
Use a consistent configured window and denominator definition within a dataset.

Target contract: race_id, feature_as_of, listed_scheduled_start_jst,
identity_evidence, entry_time_evidence, and riders with car_number and namespaced
rider_id. Cutoff must strictly precede scheduled start. Evidence must support
that this roster was known before the cutoff, not merely present in final results.

Each history race needs race_id, race_status=completed, race_start_at,
result_available_at, result_time_evidence, identity_evidence, source_use_evidence,
and participants. A participant has car_number, namespaced rider_id, status
(FINISHED/DNF/DSQ/DNS), and finish_rank (integer for FINISHED, null otherwise).
Competition ranks preserve ties (1,1,3); incomplete finish orders are rejected.
Evidence references remain operator attestations and must point to actual reviewed
records; fields or hashes alone cannot prove past availability or permission.

A history race must start within the selected window, strictly before cutoff,
and have results available strictly before cutoff. The target race itself,
conflicting duplicates, cancelled/unknown-status races and unknown identity/time
records are excluded. Cross-source aliases require verified canonical identities
upstream. No matching by car number, fuzzy name, or invented publication time.

DNF/DSQ count as starts for rates; DNS is excluded. Average finishing place uses
classified finishes only, and missing history produces null, not zero. Outputs
retain per-rider sample counts, source race IDs and record hashes with evidence
references. Retain the candidate/provenance bundle alongside the target record
and review the resulting record hash before using the historical training path.
The builder does not approve training or directly run a model.

The historical path now accepts three through nine riders and these four reviewed
numeric fields. This is separate from the prospective pipeline's existing
seven-rider requirements. Target dead heats still require a future multi-label
contract. Holdout metrics are also reported by rider count so unequal combination
spaces are visible. Synthetic verification: 33 unit tests and one 18-race end-to-end
form/training/holdout check (8/3/7; every supported rider count in test). No real
model-performance claim, source activation, collection worker or promotion.

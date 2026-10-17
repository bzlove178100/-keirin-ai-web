# keirin-ai ML pipeline

## Current stage

The repository can capture a leakage-safe `training_input` inside prospective history records and convert eligible history JSON into rider-level rows.

A record is accepted for supervised training only when all of the following are true:

- `metadata.evaluation_scope == "prospective"`
- `metadata.temporal_order == "prediction_before_result"`
- `metadata.training_eligibility.supervised_training == true`
- `training_input.schema_version == "keirin-training-input-v1"`
- `training_input.evaluation_scope == "prospective"`

Replay/legacy records remain useful for regression and smoke tests, but they are excluded from supervised training.

## Build a training table

```bash
python ml/build_training_dataset.py path/to/history-json-dir \
  --output artifacts/training-riders.csv \
  --summary artifacts/training-summary.json
```

The builder selects the latest eligible pre-result snapshot for each `race_id`, so repeated snapshots from the same race are not counted as independent races by default.

## Current row schema

Each row represents one rider in one race. Core pre-race fields include:

- race/date/venue/race number
- car number
- style
- race score
- S/H/B
- line position and line length
- recent-form fields when available
- current-meet average finish when available
- condition and bank-fit scores when available
- parsed comment factors when available
- known trifecta-odds coverage count

Targets are derived only after the race from top-level `outcome_combo`:

- `target_first`
- `target_second`
- `target_third`
- `target_top3`

Settlement odds and result timestamps are not exposed as model features.

## LightGBM position-model candidate

The first offline ML candidate preserves the existing Phase32/web contract instead of replacing it.

Implemented development flow:

1. `train_position_models.py` trains independent LightGBM LambdaRank models for 1st, 2nd, and 3rd place from rider-level prospective data.
2. Raw position-ranking scores are converted with a within-race softmax only to create normalized position distributions. They remain **uncalibrated**.
3. `trifecta_adapter.py` combines the three position distributions over all valid ordered triples.
4. A seven-rider race is required to produce exactly 210 unique trifecta combinations with probability mass approximately 1.
5. Offline validation reports position-ranking metrics plus trifecta Top-1/3/5/10 and mean reciprocal rank.
6. The generated model files are development artifacts only and are not connected to `predict-engine-dev`.

Training example after eligible prospective history has been accumulated:

```bash
python ml/build_training_dataset.py path/to/history-json-dir \
  --output artifacts/training-riders.csv \
  --summary artifacts/training-summary.json

python -m ml.train_position_models artifacts/training-riders.csv \
  --output-dir artifacts/lightgbm-position-models-v1
```

The trainer currently uses rider performance, line, recent-form, condition, bank-fit, and parsed-comment fields as model features. Prediction-time trifecta odds are not used as model features; odds-band selection remains a later layer.

## Offline inference

`predict_position_models.py` loads the three saved model files and runs the same rider-feature extraction used by the training dataset. This reduces training-serving skew before any API integration is attempted.

```bash
python -m ml.predict_position_models path/to/pre-race.json \
  --model-dir artifacts/lightgbm-position-models-v1 \
  --output artifacts/offline-prediction.json
```

The offline inference result contains:

- first/second/third rider distributions and rankings
- all valid ordered trifecta combinations
- exactly 210 combinations for a seven-rider race
- normalized trifecta mass
- confirmed prediction-time odds when present
- an audit of K-Dreams `9999.9` no-ticket markers removed from odds metadata

The model never uses trifecta odds as model features. Unknown odds are not inferred. Attached odds are metadata only; `monetary_expected_value` remains null and `monetary_ev_enabled` remains false.

The offline runtime also refuses artifacts whose feature schema or model version does not match the current runtime, and it accepts only artifacts whose metrics identify them as completed offline-validation models with production disabled.

## Evaluation rules

- Split train/validation/test by time, not by individual rider rows from the same race.
- Never mix replay/legacy records into formal prospective accuracy claims.
- Keep all rows from the same race in the same split.
- Compare ML candidates against the preserved Phase32 baseline before promotion.
- Treat softmax-normalized LightGBM scores and the resulting trifecta table as uncalibrated until prospective calibration is validated.
- Do not enable monetary EV from uncalibrated scores.
- Do not enable production prediction, external fetching, or database writes merely because an ML model exists.

## Data sufficiency

No production-sufficiency race count is asserted here. The trainer has a small technical minimum only to prevent malformed development runs; that threshold is **not** a claim that the resulting model is statistically ready for use.

The next evidence gate is to accumulate genuine prospective, pre-result, settled records and report the observed sample size, class behavior, missing-feature coverage, chronological validation results, and comparison with the preserved Phase32 baseline. Promotion criteria should then be defined from those observed data rather than from an arbitrary race-count threshold.

## Paired chronological evaluation

Run from the repository root after installing `ml/requirements.txt`:

```bash
python -m ml.evaluate_offline path/to/history-json-dir \
  --output /path/outside/repository/evaluation.json
```

Accepts individual history records, `records` datasets and the Web export
`{"mode":"dry_run","payload":{"records":[...]}}`. Keep private input histories
and evaluation output outside this public repository.

The evaluator validates prospective eligibility, timezone-aware prediction and
result timestamps, matching training-input capture time, seven distinct riders,
and a complete normalized saved Phase32 baseline table. It rejects explicitly
marked synthetic sources in normal CLI use, replay/legacy records, missing
training inputs, conflicting duplicate snapshots and incompatible baseline
versions. It cannot independently prove that supplied timestamps or provenance
are authentic. Accepted records are user-provided history, not independently
verified live performance evidence.

It selects the latest eligible snapshot per race ID and splits distinct UTC
prediction times approximately 60%/20%/20% into training, early-stopping
validation, and untouched test periods. Simultaneous timestamps stay together.
Training labels unavailable at the validation boundary, and validation labels
unavailable at the test boundary, are purged. Five distinct prediction times
and nonempty partitions are only technical requirements, not statistical
sufficiency or promotion criteria. Preserve stable race IDs across exports.

The same test races are scored by the candidate and their saved baseline.
The report includes paired Top-1/3/5/10, reciprocal rank, clipped log loss
(probability floor 1e-15), multiclass Brier sum, candidate-minus-baseline deltas,
partition race IDs, exclusion reasons and missing-feature coverage. Lower log
loss and Brier are better; higher rank metrics are better. No ROI or betting
recommendation is inferred. Both probability tables remain uncalibrated.

Insufficient eligible data produces a report with a blocked reason and exit
code 2; no model is trained. The command does not save or promote model files,
write a database, fetch external data, or change deployed functions. Repeatedly
using this test period to choose models makes it development data; reserve a
new untouched period for the next final evaluation.


## Offline result page (7/9 riders)

The existing inference CLI can now write a self-contained HTML preview alongside JSON:

```sh
python -m ml.predict_position_models synthetic-race.json \
  --model-dir synthetic-models --output prediction.json \
  --html-output prediction.html
```

The page contains five categories, the top ten trifecta scores, all three position rankings, the complete
210/504-combination table, partial confirmed-odds coverage and OFF/uncalibrated labels.
It has no scripts or external resources, and can be opened without a server. This is
an offline output connection; it does not run LightGBM inside the browser or connect
the candidate to the hosted prediction API. Model evidence_scope is a recorded label,
not an authenticity or licensing attestation. Missing scope is displayed as unverified.

JSON `selected_predictions` and the page use the existing five-category policy: the
top three model scores first, then confirmed odds in [20,60), [60,100), [100,500),
and [500,infinity), with at most three per category and no cross-category duplicates.
Insufficient categories remain partial or skipped; missing odds are not filled.
`ml.category_selection` is a Python adaptation, parity-tested against the actual
TypeScript Phase32 selector. It does not reuse Phase32 scoring or feature explanations.
Stable score ties retain table order. Model scores remain uncalibrated and monetary
EV remains disabled. Older preview JSON without selection is rendered using this
policy; if selection is supplied, it must match the model table exactly.

Only standard integer rosters 1..7 or 1..9 are accepted by this inference CLI. Missing
riders/dead heats are explicitly held outside ordinary scoring (see below). Model metadata version and feature columns
must match the runtime, as must the existing model/schema checks. Saved/unlicensed real
data must not be trained or used to resume acquisition; source HOLD remains in force.

For a reproducible synthetic train/save/reload/inference/page check:

```sh
PYTHONPATH=. OMP_NUM_THREADS=2 python tests/ml_position_smoke.py
python -m unittest discover -s tests -p 'test_offline_preview.py'
python -m unittest discover -s tests -p 'test_category_selection.py'  # Node 24 for parity
```

The smoke generates all records in code (mixed 7/9, 16 races, 128 rider rows), and
uses temporary model files. Optional KEIRIN_SMOKE_ARTIFACT_DIR retains only generated
prediction JSON/HTML for visual checks. It never reads private source datasets.

## Frozen model history and review (synthetic only)

The same smoke now exercises actual CLI capture, settlement and review for both
7 and 9 riders after reloading the saved models. `model_artifact.sha256` identifies
the five saved model/schema/metrics files; `trained_at` is recorded metadata, not
an independently verified training cutoff. A digest is not a signature or use permission.

```sh
python -m ml.model_history capture prediction.json --synthetic --output snapshot.json
python -m ml.model_history settle snapshot.json synthetic-settlement.json --synthetic --output history.json
python -m ml.model_history evaluate history.json --synthetic --output review.json
```

Capture requires generated synthetic model evidence, complete 7/9 scores and saved
categories, a model file digest, timezone-aware training/inference/capture/scheduled
timestamps in order, and `race.scheduled_start_jst`. The race date must match the
scheduled date in Japan. Its clock is local/unverified. Every output is created
exclusively: an existing path is never overwritten.

Settlement input contains the snapshot's exact `race_id`, `outcome_combo`, positive
`settlement_odds`, and timezone-aware `result_timestamp` at/after scheduled start.
The generated smoke uses synthetic future result timestamps to simulate this
sequence; it does not assert that a real result was already confirmed. Result fields
remain outside the frozen prediction and do not replace prediction-time odds.

The distinct schemas `ml-prediction-snapshot-v1` and `ml-settled-history-v1` must not
be passed off as Phase32 snapshots or training-eligible `backtest-record-v2` records.
Review validates each saved snapshot, selects the latest valid snapshot per race,
excludes conflicting settlements/tied snapshots, and reuses the existing rank,
top-k, log-loss and Brier metrics. It also reports category selection counts/hits.
No model is retrained. This is a frozen synthetic prediction review, **not** the
existing paired Phase32/LightGBM holdout or evidence of real predictive quality.
No ROI, monetary EV, training eligibility or promotion is enabled.

```sh
python -m unittest discover -s tests -p 'test_model_history.py' -v
```

The owner Web/API and browser history tools do not yet import these ML schemas.
Real-data authorization, trustworthy pre-race capture and data lineage require
separate review before this synthetic-only path can be extended.

## Synthetic browser workbench

With the existing ML dependencies installed, start the development UI:

```sh
OMP_NUM_THREADS=2 python -m ml.synthetic_workbench --synthetic
```

Open the printed loopback URL in the **same environment**. Choosing 7 or 9 riders
trains a generated model once, runs existing inference, and captures the prediction
before displaying the five categories. Enter a synthetic result to settle the frozen
prediction and view the existing review metrics. The full-score preview and snapshot,
settled history, combined histories and review JSON are available as downloads.
Refreshing the page retains server-session state and the recorded result.

This is a local development workbench, not the deployed owner Web/API or a public
smartphone URL. Binding is fixed to `127.0.0.1`; there is no remote-host option.
It accepts only generated 7/9 fixtures, not race uploads, arbitrary paths or URLs.
POSTs require same-origin/Host checks and a JSON-only custom header; cross-site
requests are rejected. No existing authentication or Supabase settings are changed.
See Python's [HTTP server documentation](https://docs.python.org/3.12/library/http.server.html)
for the development-only server's deployment limits. Do not expose it using a public tunnel.

Models are temporary to the process. Records default to temporary storage; use the
optional local session directory below to resume them after process exit. Each session
holds at most 20 snapshots. Licensed real-data entry remains disabled.
The shared `ml.synthetic_demo.make_record` is the original generated smoke fixture,
moved without changing its content. No private source files are read or trained.

```sh
OMP_NUM_THREADS=2 python -m unittest discover -s tests -p 'test_synthetic_workbench*.py' -v
# CI uses its existing Chrome and Playwright setup for the interactive flow:
node tests/test_synthetic_workbench_ui.cjs
```


## Declared conditions and held results (synthetic only)

Generated fixtures declare `race_conditions` as
`{"race_status":"scheduled","withdrawn_car_numbers":[]}`. When this object is
present, inference rejects missing/extra keys, other statuses, and any withdrawal
before loading a model; the same check protects preview/snapshot capture. Older
inputs without this field remain readable, **not independently verified as having
no withdrawals**. Provider-specific flags are not parsed here: a future authorized
adapter must map them to this contract and reject unknown conditions. No actual
provider data is fetched or inferred from a missing field.

Normal settlement keeps its existing four fields and optionally accepts
`"result_status":"normal"`. No other fields are silently discarded. For a nonstandard
result, use the same `settle` CLI with this synthetic event instead:

```json
{
  "race_id": "<exact snapshot race_id>",
  "result_timestamp": "2026-10-17T11:10:00+09:00",
  "result_status": "withdrawn",
  "withdrawn_car_numbers": [7]
}
```

Allowed held statuses are `dead_heat`, `withdrawn`, and `cancelled`. Only `withdrawn`
requires a nonempty list of distinct integer car numbers from the original roster.
For the other two statuses omit that list. Do not supply outcome/odds for a held
record. All event times must be at/after capture; normal/dead-heat results must also
be at/after scheduled start. The example time must be replaced with a time consistent
with the generated snapshot. Cancellation/withdrawal can occur before start.

The output schema is `ml-held-history-v1`, preserving the frozen prediction and
reason without fabricating a winner, payout or training eligibility. Any valid hold
excludes **all** records for that race, including later ordinary records. Evaluation
returns `held_races` and `held_cases`; `excluded` counts excluded records. Held races
do not enter hit-rate/log-loss/Brier denominators. Unrelated ordinary races retain
their metrics. If all races are held, metrics are empty and evaluation is blocked
(the CLI writes the report and exits 2). No hold-resolution/override is provided.

The workbench result-state selector records these same events, hides ordinary
finish/odds fields, and retains the held reason on reload/export. This is explicit
exclusion support; it does not implement 6/8-rider inference, multiwinner scoring,
refund calculations, or real event verification.


## Resume a local synthetic session

On the tested Linux/POSIX development environment, opt into checkpoint storage with
a directory **outside the repository** on a retained local disk:

```sh
OMP_NUM_THREADS=2 python -m ml.synthetic_workbench --synthetic --state-dir /absolute/path/keirin-synthetic-session
```

Restart with the same directory to restore saved predictions, normal/held results,
and the selected record. Choose any saved prediction from the resume list, including
an unfinished prediction. Its original model scores, model identifier and schedule
are preserved; reviewing/settling it does not train a model. A new prediction trains
only the code-generated fixture when necessary; model files are not persisted or
loaded from the session. After the active synthetic start time passes, new predictions
receive a new race number/series so they cannot overwrite an earlier race's review.

The browser shows temporary/automatic-save/restored/error status. Predict, settle,
hold and selection changes are acknowledged only after the configured checkpoint
write succeeds. The full-session download includes unfinished predictions; the
existing history/review downloads remain available. There is no browser file-upload
or arbitrary path/URL input. Only this workbench's generated synthetic records belong
in the fixed `synthetic-session.json` file. This is not a licensed real-data importer.

The session store has a versioned schema, a 32 MiB limit, an integrity digest, strict
snapshot/history cross-checks, a nonblocking process lock, regular-file/no-symlink
checks, and write→flush→fsync→atomic replacement→directory fsync. Corrupt/incompatible
state fails startup without falling back to an empty session. External file changes
are not overwritten. An error before replacement leaves the old checkpoint and memory;
an error after replacement reports an uncertain save, stops writes and requires a
restart to reconcile the complete checkpoint. Do not blindly resubmit a failed action.
Interrupted `.partial` files are ignored, never loaded as a checkpoint.

Implementation references: Python [file replacement/fsync](https://docs.python.org/3.12/library/os.html)
and [process locking](https://docs.python.org/3.12/library/fcntl.html). Hashes are not
signatures or permission evidence, and locks only coordinate cooperating processes.
The tests cover process restart/SIGKILL and injected filesystem errors, not real power
loss, disk loss or network filesystems. Keep independent exports: a checkpoint in a
transient workspace is not a backup. Windows persistence and multi-host sharing are
not qualified. No authentication changes, Supabase/DB writes or public hosting occur.
At the 20-record limit use a new empty session directory after exporting; restarting
the same directory does not clear records or reset the limit.

```sh
node tests/test_synthetic_workbench_restart_ui.cjs  # CI Chrome + Playwright
```

## Display frozen ML predictions with the existing Web renderer

In the synthetic workbench, open **既存Web形式で表示** after selecting a prediction.
The loopback-only `/api/model-view/<snapshot-id>` endpoint validates the frozen
synthetic snapshot and projects `keirin-ml-web-response-v1`. It includes race/model
identity, capture time, odds coverage and the five category picks; it excludes full
score tables, histories and arbitrary metadata. `/web-view/<snapshot-id>` loads only
the current `index.html` functions `appendPick` and `renderCategory`, plus the separate
`model-web-response.js` validator. No owner bootstrap, live prediction API or Phase32
history capture runs. Changes to the two renderer boundaries fail closed; CI includes
`index.html` changes so compatibility can be checked before integration.

The browser rejects mismatched request/response snapshot IDs, unknown versions,
unsafe flags and invalid category picks, and clears stale results on failure. It
uses only the fixed local endpoint, without credentials or redirects. The server
validates the full source prediction; the projected browser response cannot prove
ranking against omitted candidates. Digests are identifiers/integrity checks, not
signatures or authentication. Authentication and entitlement are explicitly
`not_asserted`; this endpoint must not be published as a subscription API.

This proves renderer compatibility for generated synthetic predictions. The deployed
owner Web/API is not connected to ML by this change; authentication, member-plan
filtering, cloud execution/storage and publication remain separate unfinished work.

```sh
python -m unittest discover -s tests -p 'test_synthetic_workbench_web_response.py' -v
node tests/test_synthetic_workbench_ui.cjs  # CI Chrome: actual 7/9 output and rejected responses
```

## Prepare a synthetic owner API artifact (no deployment)

The existing `predict-engine-dev` entry point now has a separate
`synthetic_model_view` mode behind its unchanged Auth user lookup and exact
`role=owner` plus `plan=owner` checks. It serves **frozen synthetic predictions**,
not on-demand Python inference. Its checked-in `synthetic_model_views.ts` is null:
an owner request gets HTTP 503 until a reviewed server artifact exists. An
authenticated GET reports availability and the saved snapshot IDs. The new POST
accepts only `{"mode":"synthetic_model_view","snapshot_id":"<32 hex characters>"}`.
Caller-provided predictions, bundles, race inputs or URLs are rejected.

Generate a package in a **new directory outside the checkout**:

```sh
OMP_NUM_THREADS=2 python -m ml.synthetic_model_bundle --synthetic --output-dir /absolute/new/path/keirin-owner-synthetic
```

This reuses the code-generated workbench fixture to train one model set and capture
one 7-rider and one 9-rider prediction. It validates each full snapshot, projects
only the existing Web display contract, and writes `synthetic_model_views.ts` plus
`bundle_receipt.json` with the module SHA-256, snapshot/model identifiers and
`deployed:false`. It accepts no real records, existing model/session files, URLs or
credentials. Existing directories and checkout destinations are refused. A failed
generation may leave an incomplete directory; no success receipt means it is not
a completed package. Use a new output directory after correcting the cause.

The generator does not replace the checked-in null module, upload a file, register
credentials, change access, or deploy anything. The generated module is for a
separately reviewed deployment package only. Never place real predictions/models
in this public repository. The server validates both saved views using the same
browser contract and returns 503 for an invalid bundle, 404 for an unknown ID.
The owner response wraps the view without claiming a new prediction or DB save.
The nested view's `not_asserted` authentication fields describe the portable data;
only the entry point adds authenticated owner claims after its existing verifier.

Local tests run the real TypeScript handler with Node Web APIs and synthetic
Auth/profile responses; no real identity service is called. CI also checks the
Deno module graph. These checks are not deployed Edge execution, real account
authentication, scheduled model generation, member-plan enforcement or production
acceptance. Public Web integration and approved hosting remain unfinished.

```sh
python -m unittest discover -s tests -p 'test_synthetic_workbench_owner_api.py' -v
```

## Prepare the owner Web connection for review

`python -m ml.prepare_owner_web_preview --output-dir /tmp/keirin-owner-web-review`
creates a new directory with a candidate `index.html`, its three script
dependencies, `owner-web-integration.patch`, and a SHA-256 receipt. The directory
must be outside the checkout and must not already exist. It never applies the
patch, replaces repository files, uploads, or deploys. Missing/duplicate source
anchors and already-prepared HTML are rejected.

The candidate uses the existing login/session refresh and authenticated GET/POST
helpers. Its separate panel requests the server's synthetic snapshot catalog,
then sends only `mode=synthetic_model_view` and the selected snapshot ID. The
server still checks owner role **and** owner plan. A null server bundle shows
"not prepared"; it is not silently replaced by example results. Five categories
are rendered through the existing renderer into separate DOM IDs, without
changing the real-race input, Phase32 snapshot, or history pipeline.

Review this generated patch together with PR #259's `index.html` changes. The
integration anchors were also checked against #259 head `d688e810`; recheck the
current file before applying. The patch adds only a panel host, script includes,
the adapter initialization, and reset calls on logout/session clearing. The
repository `index.html` is intentionally not edited by this preparation step.

The candidate still contains the existing application's API URLs. Do not treat
opening it as an offline test: the complete-page CI intercepts every network
request and substitutes synthetic authentication. Actual login, bundle
placement, hosting, deployment and production operation require their existing
separate approvals. Tests of this candidate do not establish real-service
availability or prediction accuracy.

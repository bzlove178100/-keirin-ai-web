# Prospective real-race collection protocol

Purpose: collect leakage-resistant real-race histories for paired Phase32 baseline vs LightGBM offline evaluation.

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

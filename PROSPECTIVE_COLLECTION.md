# Prospective real-race collection protocol

Purpose: collect leakage-resistant real-race histories for paired Phase32 baseline vs LightGBM offline evaluation.

## Required order

For each race:

1. Before scheduled start, use only information available at prediction time.
2. Enter the scheduled start in Japan time and explicitly confirm the race has not started.
3. Run owner-only Phase32 dry-run and save the prediction snapshot before scheduled start.
4. Do not edit the saved snapshot after the race.
5. After the official result is available, enter the confirmed trifecta outcome, settlement odds and result timestamp.
6. Generate history through `history-pipeline-dev` and save the history JSON.
7. Confirm the generated record is prospective and supervised-training eligible before adding it to the evaluation dataset.

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

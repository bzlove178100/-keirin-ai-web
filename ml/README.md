# keirin-ai ML pipeline

## Current stage

The repository can now capture a leakage-safe `training_input` inside prospective history records and convert eligible history JSON into rider-level rows.

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

## Planned LightGBM integration

The first ML candidate should preserve the existing Phase32 interface rather than replacing the web/API contract.

Proposed flow:

1. Train position-specific models for 1st, 2nd, and 3rd place using rider-level prospective data.
2. Score every rider for each position.
3. Generate all valid ordered triples.
4. Combine the three position scores for each triple.
5. Normalize across all valid triples to produce a 210-combination probability table for a seven-rider race.
6. Compare against the current Phase32 baseline using the existing backtest metrics.
7. Calibrate probabilities only after enough prospective validation data exists.
8. Keep odds-band selection separate from raw model scoring; monetary EV remains disabled until probability calibration is validated.

## Evaluation rules

- Split train/validation/test by time, not by individual rider rows from the same race.
- Never mix replay/legacy records into formal prospective accuracy claims.
- Keep all rows from the same race in the same split.
- Compare ML candidates against the preserved Phase32 baseline before promotion.
- Do not enable production prediction, external fetching, or database writes merely because an ML model exists.

## Data sufficiency

No fixed minimum race count is asserted here. The repository should first accumulate prospective, pre-result, settled records and report the actual class balance and coverage. Model training and promotion criteria should be decided from those observed data rather than from an arbitrary threshold.

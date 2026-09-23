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

python ml/train_position_models.py artifacts/training-riders.csv \
  --output-dir artifacts/lightgbm-position-models-v1
```

The trainer currently uses rider performance, line, recent-form, condition, bank-fit, and parsed-comment fields as model features. Prediction-time trifecta odds are not used as model features; odds-band selection remains a later layer.

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

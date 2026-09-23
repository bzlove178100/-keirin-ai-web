# Offline LightGBM ranking pipeline

This directory contains the first supervised ML path for `keirin-ai`. It is deliberately offline and is **not connected to production prediction**.

## Goal

Train a ranker that orders every possible trifecta combination within a race. For a 7-rider race this creates 210 ordered combinations and exactly one positive target: the official result.

## Leakage guardrails

Only history records are accepted when all of the following are explicit:

- `metadata.evaluation_scope == "prospective"`
- `metadata.temporal_order == "prediction_before_result"`
- `metadata.training_eligibility.supervised_training == true`
- `training_input.evaluation_scope == "prospective"`
- pre-race rider features exist in `training_input.players`

Replay/legacy records are excluded from supervised training.

The model feature matrix does **not** include settlement odds, result timestamps, result combinations, or prediction-time odds. Prediction-time odds are kept only as analysis metadata. This preserves the current architecture where the core model ranks all combinations and odds are used later for confirmed-odds category filtering.

## Files

- `build_trifecta_dataset.py`: converts eligible history JSON records into one row per ordered trifecta.
- `train_lightgbm_ranker.py`: chronological train/validation split and offline LightGBM `LGBMRanker` training.
- `requirements.txt`: offline training dependencies.

## Operational training gate

`train_lightgbm_ranker.py` defaults to a minimum of 200 eligible prospective races. This is only an operational guardrail to prevent accidental training on a tiny sample; it is not a claim that 200 races are statistically sufficient for production use.

Example after enough prospective records have been collected:

```bash
python ml/build_trifecta_dataset.py history/*.json \
  --output ml/data/trifecta_ranking.csv \
  --manifest ml/data/trifecta_ranking.manifest.json

python ml/train_lightgbm_ranker.py ml/data/trifecta_ranking.csv \
  --model-out ml/artifacts/lightgbm_trifecta_ranker.txt \
  --metrics-out ml/artifacts/lightgbm_trifecta_ranker.metrics.json
```

The trained artifact outputs ranking scores, **not calibrated hit probabilities**. Probability calibration remains a separate later phase and the model must not be connected to production prediction until prospective validation criteria are defined and passed.

# Work status

Updated: 2026-09-24 UTC.

## Current checkpoint

- Resume branch: `dev-lightgbm-offline-inference-v1`; completes saved LightGBM first/second/third model inference into ordered trifecta scores.
- Earlier position-model training is merged in PR #7. Offline inference PR review/merge is the current task; check live GitHub status before resuming.
- Baseline commit c3a8019b741e1cde3d35f5db12745850bfd14f37 passed both GitHub regression and LightGBM train/inference smoke workflows.
- On 2026-09-24, local regression, ML dataset, trifecta adapter and synthetic train/inference smoke tests passed after rejecting non-finite, boolean and invalid-combination odds. Module CLI help also passed. Final remote CI must be checked against the PR head.
- CLI examples use `python -m ml.predict_position_models` and `python -m ml.train_position_models` from the repository root.
- Supabase function inventory: predict-engine-dev v16, backtest-engine-dev v5, history-builder-dev v6, history-pipeline-dev v6 ACTIVE. Inventory only; this session has not deployed functions or executed authenticated production predictions.

## Constraints

Keep production prediction, DB writing and external automatic data fetching OFF. Offline ML remains uncalibrated; monetary EV is disabled. Synthetic smoke success is not evidence of real-race accuracy. Never fabricate missing odds or claim replay records as prospective results.

## Next evidence gate

After the offline inference PR passes and is merged, build the real-data evaluation workflow: validate user-provided prospective settled records, report accepted/excluded counts and missing-feature coverage, use chronological race-level holdout, and compare the offline candidate against the preserved Phase32 baseline. Do not request a missing old snapshot again; proceed with available fixtures for technical checks and explicitly distinguish them from prospective data.

## Resume procedure

Read this file, current branch/PR status and actual source. Prefer current repository evidence over the older external handoff. The older handoff predates merged PRs #2 through #7. Do not enable production or DB writing as part of a generic resume request.

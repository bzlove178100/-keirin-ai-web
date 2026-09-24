# Work status

Updated: 2026-09-24 UTC.

## Current checkpoint

- Offline LightGBM inference was merged in PR #8, main commit `b8d1f2d5b41ffa534a26c80575dfbfada1371892`. Both PR workflows passed.
- Current work: `dev-offline-evaluation-v1`, paired chronological evaluation of new prospective history against its saved Phase32 baseline. Check live PR and CI state before resuming.
- Added strict input/time/baseline checks, latest-snapshot deduplication, train/validation/test periods, boundary purging of unavailable labels, paired ranking/probability metrics, and missing-feature/exclusion reporting.
- Fixed reading the Web's `mode=dry_run, payload.records` history export.
- Local evaluation tests cover Web input, replay/synthetic rejection, invalid timestamps/probabilities, conflicting duplicates, UTC order, boundary leakage, known metric values and synthetic end-to-end evaluation. Synthetic success is not real-race accuracy.
- Two existing saved `backtest-history-dataset-v1.json` variants were inspected. Both contain one old Ito race record and lack `training_input`; neither supports this new evaluation. No real-data accuracy result was generated.

## Next step

After this branch passes CI and is merged, obtain new user-provided prospective settled history exports containing training_input, prediction/result timestamps and full baseline trifecta scores. Run `python -m ml.evaluate_offline ... --output ...` outside the public repository. Inspect exclusions and data coverage before interpreting any metrics. Do not request the unavailable old prediction snapshot again. Never substitute synthetic or replay results for prospective accuracy evidence.

## Constraints

Production prediction, DB writing and external automatic data fetching remain OFF. Offline scores remain uncalibrated; monetary EV and promotion are disabled. This change does not deploy Supabase functions or change the public Web UI. Do not commit private histories, model artifacts or evaluation reports. Timestamp validation checks supplied data consistency, not independent provenance.

## Resume

Read this file and current GitHub state. Prefer current repository evidence over the old external handoff, which predates merged development PRs. Verify current branch/commit and tests before changing code.

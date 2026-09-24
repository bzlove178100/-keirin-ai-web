# Work status

Updated: 2026-09-24 UTC.

## Verified progress

- PR #8: offline LightGBM inference merged.
- PR #9: paired chronological evaluation merged at `e1ce9de4618cf8fb17f60333a2e3ec87c32b6264`; regression and ML evaluation checks passed.
- Prospective capture checks are on `main`: Japanese-time scheduled start, explicit pre-start confirmation, capture/save cutoff checks, future result-time rejection, training-input readiness feedback and full finite 210-combination probability-table validation.
- First new real-race prospective snapshot was captured before the scheduled start for 2026-09-24 Ito Onsen 1R. The snapshot is marked prospective and contains seven riders, all 210 model probabilities and 72 confirmed trifecta odds (34.3% coverage). Unknown odds were not invented. The private snapshot remains outside the repository.
- `history-pipeline-dev` builds `keirin-training-input-v1` only from the pre-race snapshot and keeps settlement targets separate. A regression test now explicitly guards that prospective WINTICKET inputs may retain partial confirmed odds without manufacturing missing combinations.
- Real-data accuracy remains unmeasured until the race result is confirmed and the new snapshot is converted into an eligible history record. Two old saved history variants lack `training_input` and cannot supply the new evaluation.

## Validation

Run `deno test tests/training_input_test.ts`, `node tests/test_web_capture.cjs`, and existing regression/ML checks. Check the final PR CI before merging. Owner-authenticated end-to-end result settlement still requires the confirmed official outcome after the race.

## Next action

After the official result for the captured prospective race, load the saved snapshot in the Web, enter the confirmed trifecta outcome, settlement odds and result timestamp, then run `history-pipeline-dev` through the Web and save the generated history JSON. Confirm `training_input_present=true` and `supervised_training_eligible=true`, add the record to the chronological dataset, and run the paired baseline-vs-LightGBM evaluation. Repeat across additional prospective races before interpreting accuracy or calibration.

## Constraints

Keep production prediction, DB writing and external automatic fetching OFF. Scores remain uncalibrated; monetary EV and promotion remain disabled. Do not commit private histories, snapshots, model artifacts or evaluation reports. Prefer current GitHub state to older external handoff notes.

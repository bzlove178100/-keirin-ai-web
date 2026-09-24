# Work status

Updated: 2026-09-24 UTC.

## Verified progress

- PR #8: offline LightGBM inference merged.
- PR #9: paired chronological evaluation merged at `e1ce9de4618cf8fb17f60333a2e3ec87c32b6264`; regression and ML evaluation checks passed.
- Current branch: `dev-prospective-capture-checks-v1`. Adds Japanese-time scheduled start and explicit pre-start confirmation to Web snapshot capture, capture/save cutoff checks, future result-time rejection, training-input readiness feedback and full finite probability-table validation.
- Date-only legacy snapshots remain available for replay diagnostics but are no longer classified as prospective by the Web. No Supabase functions are changed; these are client consistency checks, not server-attested timing or independent provenance checks.
- Real-data accuracy remains unmeasured. Two old saved history variants lack training_input and cannot supply the new evaluation.

## Validation

Run `node tests/test_web_capture.cjs` and existing regression checks. The Web test executes actual inline functions and covers scheduled cutoff, legacy scope, invalid probability tables, unavailable training inputs and future result submission. Check the final PR CI and GitHub Pages deployment before claiming public delivery. Owner-authenticated end-to-end execution still requires a real session and race input.

## Next action

Use a new, not-yet-started race input. Enter its scheduled start in Japan time, confirm it has not started, run dry-run and save the snapshot before the scheduled start. After the official result, enter confirmed outcome, odds and result timestamp; generate and save history. The Web displays whether basic training fields are present. Feed multiple eligible histories into `python -m ml.evaluate_offline ... --output ...` outside this public repository. Exclusions and technical minimums are not proof of statistical sufficiency. Do not ask for the unavailable old snapshot again.

## Constraints

Keep production prediction, DB writing and external automatic fetching OFF. Scores remain uncalibrated; monetary EV and promotion remain disabled. Do not commit private histories, model artifacts or evaluation reports. Prefer current GitHub state to older external handoff notes.

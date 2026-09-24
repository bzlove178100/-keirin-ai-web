# Work status

Updated: 2026-09-24 UTC.

## Verified progress

- PR #8: offline LightGBM inference merged.
- PR #9: paired chronological evaluation merged at `e1ce9de4618cf8fb17f60333a2e3ec87c32b6264`; regression and ML evaluation checks passed.
- Prospective capture checks are on `main`: Japanese-time scheduled start, explicit pre-start confirmation, capture/save cutoff checks, future result-time rejection, training-input readiness feedback and full finite 210-combination probability-table validation.
- First new real-race prospective snapshot was captured before the scheduled start for 2026-09-24 Ito Onsen 1R. The snapshot is marked prospective and contains seven riders, all 210 model probabilities and 72 confirmed trifecta odds (34.3% coverage). Unknown odds were not invented. The private snapshot remains outside the repository.
- The public result for that race has since been confirmed. A private prospective history record was generated outside the repository using the confirmed outcome/settlement odds and a timezone-aware result-observation timestamp. Contract checks confirm the history has seven riders, all 210 Phase32 probabilities, the original 72 known pre-race odds, pre-result temporal order and supervised-training eligibility. The private history remains outside the repository.
- PR #13 added `ml.collection_status`, which reports prospective collection progress without training and keeps the five-distinct-time requirement explicitly separate from statistical sufficiency.
- PR #14 added `ml.settle_snapshot`, a network-free offline settlement fallback that validates the saved snapshot and emits the canonical private history shape without database writes or production changes.
- Current real prospective collection status is one eligible distinct prediction time. Four additional distinct eligible prediction times are required to reach the paired evaluator's five-time technical minimum. Boundary purging can still require more than five races/times.
- Two old saved history variants lack `training_input` and cannot supply the new evaluation.

## Validation

CI currently covers Web capture/cutoff checks, ML dataset safety, collection readiness, offline snapshot settlement, trifecta adaptation, Phase32 contracts and training-input sanitization. LightGBM position-model smoke and chronological leakage checks remain required before merging ML-affecting changes.

For private history collections, run:

```bash
python -m ml.collection_status /path/to/private/histories --require-ready
```

When the technical minimum and chronological partitions are available, run the paired offline evaluation only on private histories. Do not commit real histories, snapshots, model artifacts or evaluation reports.

## Next action

Collect additional prospective races in chronological order. For each race, capture the immutable snapshot before scheduled start, settle it only after the confirmed result is available, then verify supervised-training eligibility. Prefer settling earlier races before later evaluation boundaries so labels are available and fewer records are purged.

After enough eligible distinct prediction times exist, run paired Phase32-vs-LightGBM offline evaluation. Treat the first five-time pass only as a technical pipeline milestone, not as evidence of model superiority, calibration or profitability.

## Constraints

Keep production prediction, DB writing and external automatic fetching OFF. Scores remain uncalibrated; monetary EV and promotion remain disabled. Do not commit private histories, snapshots, model artifacts or evaluation reports. Prefer current GitHub state to older external handoff notes.

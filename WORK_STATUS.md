# Work status

Updated: 2026-09-24 UTC.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is the authoritative shared goal for this repository. The final product direction is a broad autonomous AI agent, not a keirin-only development assistant. Keirin AI remains the first major execution target and its existing safety/validation requirements remain in force.

## Verified progress

- PR #8: offline LightGBM inference merged.
- PR #9: paired chronological evaluation merged at `e1ce9de4618cf8fb17f60333a2e3ec87c32b6264`; regression and ML evaluation checks passed.
- Prospective capture checks are on `main`: Japanese-time scheduled start, explicit pre-start confirmation, capture/save cutoff checks, future result-time rejection, training-input readiness feedback and full finite 210-combination probability-table validation.
- First new real-race prospective snapshot was captured before the scheduled start for 2026-09-24 Ito Onsen 1R. The snapshot is marked prospective and contains seven riders, all 210 model probabilities and 72 confirmed trifecta odds (34.3% coverage). Unknown odds were not invented. The private snapshot remains outside the repository.
- The public result for that race has since been confirmed. A private prospective history record was generated outside the repository using the confirmed outcome/settlement odds and a timezone-aware result-observation timestamp. Contract checks confirm the history has seven riders, all 210 Phase32 probabilities, the original 72 known pre-race odds, pre-result temporal order and supervised-training eligibility. The private history remains outside the repository.
- PR #13 added `ml.collection_status`, which reports prospective collection progress without training and keeps the five-distinct-time requirement explicitly separate from statistical sufficiency.
- PR #14 added `ml.settle_snapshot`, a network-free offline settlement fallback that validates the saved snapshot and emits the canonical private history shape without database writes or production changes.
- PR #21 added prospective collection progress to the public Web dataset section. After eligible history JSONs are loaded locally, the page shows `前向き実データ x/5件` and the remaining distinct prediction times. The page does not discover private histories automatically.
- PR #22 replaced the temporary write-capable UI application workflow with a persistent read-only regression workflow.
- PR #23 tightened scheduled-start causality end to end: new prospective settlement rejects snapshots captured at or after scheduled start, rejects result observation timestamps before scheduled start, and checks equivalent saved scheduled-start fields. The same schedule-order guard is covered in supervised-training/browser-local readiness paths. Legacy records that predate scheduled-start capture remain readable at the dataset boundary.
- PR #25 refreshed `AGENTS.md` and this status file against the repository state then current.
- PR #26 added a browser-local private history bundle export. On a phone, a previous bundle and new per-race history JSONs can be selected together and saved as one local JSON. Only fully identical records are removed; conflicting non-identical records are preserved for downstream validation. The bundler makes no network request and writes no database.
- PR #27 added a visible launcher in the main Web header for `prospective-tools.html`, so the browser-local settlement/readiness/bundle workflow is reachable without manually editing the URL.
- PR #29 replaced the main Web's count-only prospective progress decision with the same strict browser-local `ProspectiveTools.collectionStatus` validator used by the dedicated prospective tool. The Web distinguishes reaching five eligible prediction times from an actually available leakage-safe chronological train/validation/test split and surfaces the block reason when boundary purging still prevents evaluation.
- PR #30 removed the one-shot write-capable migration workflow and returned strict readiness verification to persistent read-only regression.
- PR #31 (`13fa28c141fb0ba4b7a45a9dd62a43f5baaecb57`) made the evaluator reuse the shared strict prospective evaluation protocol so readiness and paired offline evaluation are locked to one preparation/split contract.
- Current real prospective collection status is one eligible distinct prediction time. Four additional distinct eligible prediction times are required to reach the paired evaluator's five-time technical minimum. Boundary purging can still require more than five races/times.
- Two old saved history variants lack `training_input` and cannot supply the new evaluation.

## Validation

CI covers Web capture/cutoff checks, browser-local prospective tools, private-history bundle behavior, the main-Web prospective-tools launcher, strict collection-readiness UI state, ML dataset safety, collection readiness, offline snapshot settlement, scheduled-start causality, trifecta adaptation, Phase32 contracts, training-input sanitization, LightGBM position-model smoke and paired chronological leakage checks.

The strict preparation path validates prospective scope, training schema, timezone-aware chronology, scheduled-start causality when available, seven riders/styles, Phase32 engine version, complete finite 210-combination baseline probabilities, outcome membership, duplicate/conflict rules and chronological boundary purging.

For private history collections, run:

```bash
python -m ml.collection_status /path/to/private/histories --require-ready
```

When the technical minimum and chronological partitions are available, run the paired offline evaluation only on private histories. Do not commit real histories, snapshots, model artifacts or evaluation reports.

## Common agent gap

The repository has strong keirin-specific validation, Web and offline evaluation infrastructure, but the broad autonomous-agent runtime is not yet implemented. In particular, there is no verified common Task model, persistent task-state store, generic tool router, execution runner, recovery loop, cross-task activity ledger, or 21:00 sales/activity reporting runtime.

Do not describe Work/Chat tool use itself as a completed independent autonomous agent.

## Next action

Prioritize the shared agent foundation while keeping keirin collection available as a parallel data-collection track rather than the only development path.

Next implementation slice:

1. Define a machine-readable common Task model covering goal, inputs, allowed actions, completion conditions, verification requirements, artifacts, retries and blocked state.
2. Add a persistent local-safe task/activity state format with stable IDs and duplicate-prevention semantics.
3. Implement a dependency-light runner/verifier loop that can execute a safe mock/GitHub-oriented task and resume without repeating completed steps.
4. Add tests for idempotent resume, blocked-task handling, artifact-state separation and activity ledger output.
5. Adapt one existing keirin development workflow to the common Task model without enabling production prediction, DB writing or external automatic fetching.
6. Keep the 21:00 report requirement in the shared contract; connect scheduling only after sales source, accounting rules and delivery destination are known.

Do not automatically return to asking the user for race screenshots or JSON when the next safe development step can be completed without user action.

## Constraints

Keep production prediction, DB writing and external automatic fetching OFF. Scores remain uncalibrated; monetary EV and promotion remain disabled. Do not commit private histories, snapshots, model artifacts or evaluation reports. Do not commit secrets, credentials, private file identifiers or personal data. Prefer current GitHub `main` and current tests to older external handoff notes.

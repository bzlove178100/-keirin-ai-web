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
- PR #32 (`acdb0f40febc4500b4d0fd64f37897d5fbb7ee86`) added `AI_AGENT_REQUIREMENTS.md`, changed `AGENTS.md` to treat the broad autonomous-agent goal as authoritative, and moved the next development priority away from race-data collection alone.
- PR #33 (`3f01d041969bd1d3cd4304c5047313e3828cccac`) added the first shared autonomous-agent runtime core: machine-readable `TaskSpec`, atomic private task-state persistence, append-only activity ledger, explicit allowed-action gates, stable per-step idempotency keys, verifier hooks, conservative blocked/failed resume semantics, separate artifact lifecycle stages, and a keirin development-validation task adapter. Regression includes agent-core safety tests and passed before merge.
- Current real prospective collection status is one eligible distinct prediction time. Four additional distinct eligible prediction times are required to reach the paired evaluator's five-time technical minimum. Boundary purging can still require more than five races/times.
- Two old saved history variants lack `training_input` and cannot supply the new evaluation.

## Validation

CI covers Web capture/cutoff checks, browser-local prospective tools, private-history bundle behavior, the main-Web prospective-tools launcher, strict collection-readiness UI state, ML dataset safety, collection readiness, offline snapshot settlement, scheduled-start causality, trifecta adaptation, Phase32 contracts, training-input sanitization, LightGBM position-model smoke, paired chronological leakage checks and shared agent-core safety checks.

The agent-core regression verifies idempotent resume, no automatic repetition after blocked/failed states, safe retry only for explicitly `retry_safe` steps, verifier-gated completion, separate artifact state (`created`, `verified`, `persistent_saved`, `device_saved`, `ui_loaded`), task-id path safety and JSON TaskSpec round-tripping.

The strict keirin preparation path validates prospective scope, training schema, timezone-aware chronology, scheduled-start causality when available, seven riders/styles, Phase32 engine version, complete finite 210-combination baseline probabilities, outcome membership, duplicate/conflict rules and chronological boundary purging.

For private history collections, run:

```bash
python -m ml.collection_status /path/to/private/histories --require-ready
```

When the technical minimum and chronological partitions are available, run the paired offline evaluation only on private histories. Do not commit real histories, snapshots, model artifacts or evaluation reports.

## Common agent state

The first generic runtime foundation now exists and is tested, but the independent autonomous agent is not complete. The current core has no live GitHub/Supabase/Web tool adapters, no explicit reconciliation API for safely unblocking an ambiguous side effect, no scheduler/runtime host, no cross-provider tool router, and no configured 21:00 sales/activity delivery.

Do not describe Work/Chat tool use itself, or the current library-only core, as a completed independent autonomous agent.

## Next action

Continue the shared agent foundation while keeping keirin collection as a parallel data-collection track.

Next implementation slice:

1. Add an explicit reconciliation model so a blocked step can be marked `not_applied`, `applied_and_verified`, or `needs_manual_action` without blindly rerunning it.
2. Add a tool-adapter contract with capability names, required permissions, read/write classification and dry-run support, then implement a read-only GitHub adapter first.
3. Add a small orchestration entry point that loads TaskSpec JSON, private state directory and registered adapters, then runs/resumes safely.
4. Add an activity-summary/report contract. Revenue fields must support `unknown/unavailable` and must never default missing revenue to zero.
5. Preserve the 21:00 Asia/Tokyo report requirement, but connect scheduling only after the sales source, accounting rules and delivery destination are known.
6. Adapt one more real keirin development workflow to the shared runner after the GitHub adapter can verify repository/CI state without user screenshots.

Do not automatically return to asking the user for race screenshots or JSON when the next safe development step can be completed without user action.

## Constraints

Keep production prediction, DB writing and external automatic fetching OFF. Scores remain uncalibrated; monetary EV and promotion remain disabled. Do not commit private histories, snapshots, model artifacts or evaluation reports. Do not commit secrets, credentials, private file identifiers or personal data. Prefer current GitHub `main` and current tests to older external handoff notes.

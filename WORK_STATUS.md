# Work status

Updated: 2026-09-24 UTC.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is the authoritative shared goal for this repository. The final product direction is a broad autonomous AI agent, not a keirin-only development assistant. Keirin AI remains the first major execution target and its existing safety/validation requirements remain in force.

## Verified progress

### Keirin AI / prospective evaluation

- PR #8 added offline LightGBM inference.
- PR #9 added paired chronological evaluation; regression and ML evaluation checks passed.
- Prospective capture checks are on `main`: Japanese-time scheduled start, explicit pre-start confirmation, capture/save cutoff checks, future result-time rejection, training-input readiness feedback and full finite 210-combination probability-table validation.
- The first new real-race prospective snapshot was captured before the scheduled start for 2026-09-24 Ito Onsen 1R. It contains seven riders, all 210 model probabilities and 72 confirmed trifecta odds; unknown odds were not invented. The private snapshot remains outside the repository.
- The public result for that race was confirmed and a private prospective history record was generated outside the repository. Contract checks confirm pre-result chronology and supervised-training eligibility.
- PR #13 added `ml.collection_status`; PR #14 added offline snapshot settlement.
- PR #21 added prospective collection progress to the Web. PR #23 tightened scheduled-start causality. PR #26 added browser-local private history bundling. PR #27 linked the prospective tools from the main Web.
- PR #29 replaced count-only readiness with strict chronological readiness. PR #31 unified the shared strict prospective evaluation/split protocol used by readiness and paired evaluation.
- Current real prospective collection status remains one eligible distinct prediction time. Four additional distinct eligible times are required to reach the evaluator's five-time technical minimum; boundary purging can require more. Five is a pipeline minimum, not evidence of accuracy, superiority or profitability.
- Two old saved history variants lack `training_input` and cannot supply the current paired evaluation.

### Shared autonomous-agent foundation

- PR #32 added `AI_AGENT_REQUIREMENTS.md`, made the broad autonomous-agent goal authoritative, and prevented keirin data collection from becoming the only development path.
- PR #33 added the first shared runtime core: machine-readable `TaskSpec`, atomic private task-state persistence, append-only activity ledger, explicit allowed-action gates, stable per-step idempotency keys, verifier hooks, conservative blocked/failed resume semantics and separate artifact lifecycle stages.
- PR #35 added explicit blocked-step reconciliation, capability/permission metadata, orchestration preflight, a read-only GitHub adapter contract, read-only keirin status task and Asia/Tokyo daily activity/revenue report contracts. Missing revenue is represented as `unknown` or `unavailable`, never silently as zero.
- PR #37 (`d696542a5d23209644e45aee7bfb8c7a5c1e198e`) added a provider-neutral runtime bridge, strict credential-free runtime binding manifests, read-only Supabase/status and file-artifact adapter contracts, safe runtime/CLI utilities, report-delivery separation and a disabled-by-default 21:00 Asia/Tokyo schedule contract. Runtime manifests reject credential fields. All regression checks passed before merge.
- PR #38 (`1bd193a614412c1f449f5296b6d999aaa16e3359`) added `supabase/functions/agent-runtime-dev`, an owner-only hosted runtime shell with preflight-only behavior. The first CI attempt exposed only a TypeScript test-narrowing issue; it was corrected and the full regression passed before merge.
- `agent-runtime-dev` was deployed to Supabase project `keirin-ai-staging` as version 1 and verified `ACTIVE` with `verify_jwt=true`. The deployed files were read back and match the merged source. Hosted v1 does not execute tasks, persist state, perform provider writes, automatically fetch external data or deliver reports; all declared provider bindings remain unbound.
- PR #40 (`8bc1306ea1820ef19fc0fc3740d9cfa2b9da53ac`) added the first **live provider binding** for the shared agent: a GitHub Actions-hosted read-only worker using the repository's ephemeral `GITHUB_TOKEN`. It binds `github.read_main` and `github.verify_ci`, verifies required repository files and existing main-branch CI through the shared `BoundRuntime`, and explicitly blocks write capabilities.
- The new `agent runtime read-only smoke` workflow ran successfully on PR #40 with only `contents:read` and `actions:read` permissions. The ordinary keirin regression and collection-progress regression also passed before merge. This verifies a real external read-only tool path through the shared runtime without user screenshots or persistent credentials.
- Stale PR #39 was closed rather than merged after `main` advanced; this status record replaces it from current `main`.

## Validation

CI now covers Web capture/cutoff checks, browser-local prospective tools, private-history bundle behavior, main-Web readiness, ML dataset safety, collection readiness, offline settlement, Phase32/training-input contracts, shared agent-core safety, orchestration/reporting, runtime bridge/delivery behavior, hosted runtime preflight/safety, and the live GitHub read-only host bridge.

The shared agent tests verify:

- completed work is not repeated on resume;
- blocked/ambiguous side effects require explicit reconciliation;
- retry occurs only for steps marked `retry_safe`;
- artifact states distinguish `created`, `verified`, `persistent_saved`, `device_saved`, `ui_loaded`;
- preflight stops before partial execution when later actions are missing/forbidden;
- runtime capability manifests classify read/write/execute access and reject embedded credential fields;
- missing sales data never becomes `0` by default;
- 21:00 Asia/Tokyo scheduling exists only as a disabled contract until data source and destination are configured;
- hosted `agent-runtime-dev` keeps production prediction, DB writing, external automatic fetching, runtime execution and hosted persistence disabled;
- the GitHub Actions live bridge can read required repository state and verify existing CI while failing closed if required workflows are missing and refusing write capabilities.

## Current agent state

The project now has a tested generic runtime core, a real hosted Supabase preflight shell, and one verified live external-tool binding through GitHub Actions. This is no longer only a design/library exercise, but it is still not an always-on self-contained AI agent.

Still missing for independent autonomous operation:

- durable private task state outside one ephemeral Actions runner;
- a secure runtime credential/permission store for provider bindings that require non-ephemeral authorization;
- a queue/worker scheduler that can resume tasks without an active chat or one-off workflow run;
- live bindings for Supabase/files/Web and later generation services;
- sales source/accounting rules/report destination;
- image/video/text-generation adapters and broader job routing.

Do not describe current ChatGPT/Work tool use, the preflight Edge Function, or the GitHub read-only smoke worker by itself as a completed always-on agent.

## Next action

Continue the shared agent foundation while preserving the keirin track in parallel.

Next implementation slice:

1. Design hosted task-state persistence and a queue/run schema with stable task IDs, idempotency keys and states (`queued`, `running`, `blocked`, `completed`, `failed`). Do not deploy database-writing behavior until that change is explicitly authorized because the current fixed condition keeps development DB writes off.
2. Add runtime diagnostics that distinguish capability `declared`, `bound`, `authorized`, `verified` and `last_error`.
3. Add another live **read-only** binding where authorization can be safely supplied by the host, with Supabase project/function status as the preferred next candidate.
4. Preserve the live GitHub worker as a read-only verification path so future repository/CI checks do not require screenshots.
5. Keep the 21:00 Asia/Tokyo report scheduler disabled until sales source, accounting rules and delivery destination are explicitly resolved.
6. Continue prospective keirin data collection when suitable races are available, but do not let it replace common agent-runtime development.

## Constraints

Keep production prediction, development DB writing for keirin prediction flows and external automatic race-data fetching OFF. Scores remain uncalibrated; monetary EV and production promotion remain disabled. Do not commit private histories, snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current GitHub `main`, deployed function metadata and current tests to older handoff notes.

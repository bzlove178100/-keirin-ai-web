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
- PR #37 (`d696542a5d23209644e45aee7bfb8c7a5c1e198e`) added a provider-neutral runtime bridge, strict credential-free runtime binding manifests, read-only Supabase/status and file-artifact adapter contracts, safe runtime/CLI utilities, report-delivery separation and a disabled-by-default 21:00 Asia/Tokyo schedule contract. Runtime manifests reject credential fields. All new regression checks passed before merge.
- PR #38 (`1bd193a614412c1f449f5296b6d999aaa16e3359`) added the source for an owner-only hosted runtime shell, `supabase/functions/agent-runtime-dev`, with preflight-only behavior and Deno safety-contract tests. The first CI attempt failed only on TypeScript test narrowing; the test was corrected and the full regression then passed before merge.
- `agent-runtime-dev` has now been deployed to Supabase project `keirin-ai-staging` as version 1 and is `ACTIVE` with `verify_jwt=true`. Deployment metadata was read back after deployment and matches the merged source.
- Hosted runtime v1 is intentionally limited to authenticated owner status/preflight. It does **not** execute tasks, persist task state, perform provider writes, automatically fetch external data, or deliver reports. All external capabilities are declared but unbound.

## Validation

CI covers Web capture/cutoff checks, browser-local prospective tools, private-history bundle behavior, main-Web readiness, ML dataset safety, collection readiness, offline settlement, Phase32/training-input contracts, shared agent-core safety, orchestration/reporting, runtime-bridge/delivery behavior and the hosted runtime preflight/safety contract.

The shared agent tests verify:

- completed work is not repeated on resume;
- blocked/ambiguous side effects require explicit reconciliation;
- retry occurs only for steps marked `retry_safe`;
- artifact states distinguish `created`, `verified`, `persistent_saved`, `device_saved`, `ui_loaded`;
- preflight stops before partial execution when later actions are missing/forbidden;
- runtime capability manifests classify read/write/execute access and reject embedded credential fields;
- missing sales data never becomes `0` by default;
- 21:00 Asia/Tokyo scheduling exists only as a disabled contract until data source and destination are configured;
- hosted `agent-runtime-dev` keeps production prediction, DB writing, external automatic fetching, runtime execution and hosted persistence disabled.

## Current agent state

The project now has a tested generic runtime core **and** a real hosted Supabase runtime shell. This is a meaningful implementation step beyond Work/Chat-only execution, but it is not yet an always-on self-contained AI agent.

Still missing for independent autonomous operation:

- authorized live provider bindings for GitHub/Supabase/files/Web/generation services inside or behind the hosted runtime;
- persistent private task state for the hosted runtime;
- a secure secret/permission store for provider credentials;
- a worker/scheduler that can resume queued tasks without an active chat session;
- report delivery destination and sales data source/accounting rules;
- image/video/text-generation tool adapters and broader job routing.

The repository itself does not inherit ChatGPT/Work connector credentials. Do not describe current ChatGPT tool execution as the deployed agent running independently.

## Next action

Continue the shared agent foundation while preserving the keirin track in parallel.

Next implementation slice:

1. Add hosted private task-state persistence with a dedicated schema and RLS/owner-only access, but keep all provider side effects disabled.
2. Add a queue/run model (`queued`, `running`, `blocked`, `completed`, `failed`) and idempotency keys to the hosted runtime so a task can survive chat/session interruption.
3. Bind the first **read-only** live capability. Prefer GitHub repository/CI status or Supabase project/function status; do not enable write capabilities yet.
4. Add a runtime status endpoint/diagnostic record that distinguishes capability declared, bound, authorized, verified and last error.
5. Keep the 21:00 report scheduler disabled until sales source, accounting rules and delivery destination are explicitly resolved.
6. Continue prospective keirin data collection when a suitable race is available, but do not let it replace the common agent-runtime work.

## Constraints

Keep production prediction, development DB writing for keirin prediction flows and external automatic race-data fetching OFF. Scores remain uncalibrated; monetary EV and production promotion remain disabled. Do not commit private histories, snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current GitHub `main`, deployed function metadata and current tests to older handoff notes.

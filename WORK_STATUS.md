# Work status

Updated: 2026-09-25 UTC.

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

- Bound new local task states to a versioned fingerprint of the complete TaskSpec before execution. Reusing a task ID with changed input/actions/permissions/retry rules now fails without overwriting state, including after completion or interruption. Nested action arguments and task inputs are detached from callers and subsequent steps. Existing state without an identity fingerprint requires review; automatic legacy migration is intentionally absent.
- Added five task-identity tests; all 50 agent tests and existing regression checks pass locally. CI now includes task-identity coverage. Hosted persistence and distributed claim activation remain disabled.

- Fixed a local runner interruption gap: a process exit after a provider call but before completion persistence could previously repeat the operation on resume. Any attempted but incomplete step now blocks for explicit reconciliation before further tool calls. A shared nonblocking POSIX per-task file lock also prevents competing local runners/reconciliation from entering the same task. Distributed claims and durable hosted state remain unimplemented/disabled.
- Added five interruption/concurrency regression cases, including actual SystemExit during action/verification, two competing runner instances, reconciliation exclusion, between-step resume and an unresolved step omitted from the new specification. These tests do not prove distributed locking or provider idempotency.

- Added a pure queue planner and worker lifecycle contract (`AGENT_QUEUE_DESIGN.md`). It proposes owner-scoped FIFO claims with revision expectations, due-time/attempt/capacity checks, skips terminal tasks and requires reconciliation for missing/expired running leases. It does not claim tasks, perform I/O or enable hosted execution/persistence. The existing rollback-only schema still needs reviewed lease/revision fields and atomic claim operations before activation.
- Seven queue-planner regression cases cover stable ordering/no mutation, terminal skips, ambiguous lease recovery, due times/budgets, owner isolation/duplicate rejection, invalid inputs and timezone/capacity behavior. CI runs this suite alongside existing safety checks.

- PR #32 added `AI_AGENT_REQUIREMENTS.md`, made the broad autonomous-agent goal authoritative, and prevented keirin data collection from becoming the only development path.
- PR #33 added the first shared runtime core: machine-readable `TaskSpec`, atomic private task-state persistence, append-only activity ledger, explicit allowed-action gates, stable per-step idempotency keys, verifier hooks, conservative blocked/failed resume semantics and separate artifact lifecycle stages.
- PR #35 added explicit blocked-step reconciliation, capability/permission metadata, orchestration preflight, a read-only GitHub adapter contract, read-only keirin status task and Asia/Tokyo daily activity/revenue report contracts. Missing revenue is represented as `unknown` or `unavailable`, never silently as zero.
- PR #37 (`d696542a5d23209644e45aee7bfb8c7a5c1e198e`) added a provider-neutral runtime bridge, strict credential-free runtime binding manifests, read-only Supabase/status and file-artifact adapter contracts, safe runtime/CLI utilities, report-delivery separation and a disabled-by-default 21:00 Asia/Tokyo schedule contract. Runtime manifests reject credential fields.
- PR #38 (`1bd193a614412c1f449f5296b6d999aaa16e3359`) added `supabase/functions/agent-runtime-dev`, an owner-only hosted runtime shell with preflight-only behavior. The full regression passed before merge.
- PR #40 (`8bc1306ea1820ef19fc0fc3740d9cfa2b9da53ac`) added the first live provider binding: a GitHub Actions-hosted read-only worker using the repository's ephemeral `GITHUB_TOKEN`. It binds `github.read_main` and `github.verify_ci`, verifies required repository files and existing main-branch CI through the shared `BoundRuntime`, and explicitly blocks write capabilities.
- The `agent runtime read-only smoke` workflow has run successfully with only `contents:read` and `actions:read` permissions. This verifies a real external read-only tool path through the shared runtime without user screenshots or persistent credentials.
- PR #42 (`874e4e10b836355b89dbb7ea61c9e0b6b58e3b59`) added the durable hosted task-state **design**: stable task IDs, queue states (`queued`, `running`, `blocked`, `completed`, `failed`), per-user idempotency keys, owner-scoped RLS and append-only task events. The SQL is outside `supabase/migrations` and wrapped in `BEGIN ... ROLLBACK`; it is not deployed and cannot persist changes as written. Regression locks that safety boundary.
- PR #43 (`1484b1013dc85a47dc3682148625a5027d8d8d6c`) added hosted runtime capability diagnostics that explicitly distinguish `declared`, `bound`, `authorization_state`, `authorized`, `verified` and `last_error`. All provider bindings in the hosted Supabase shell remain unbound/unverified.
- `agent-runtime-dev` has been redeployed to Supabase project `keirin-ai-staging` as version 2, verified `ACTIVE` with `verify_jwt=true`, and read back after deployment. The deployed v2 source matches `main` and exposes status/diagnostics plus preflight only.
- The first v2 deployment attempt was rejected because the previous absolute import-map path was being carried into the new deployment. The cause was identified; redeployment with explicit `import_map_path="deno.json"` succeeded. No database or provider side effect occurred from the failed deployment attempt.
- Stale PR #39 was closed rather than merged after `main` advanced; its intended status information has been superseded by current records.

## Validation

CI now covers Web capture/cutoff checks, browser-local prospective tools, private-history bundle behavior, main-Web readiness, ML dataset safety, collection readiness, offline settlement, Phase32/training-input contracts, shared agent-core safety, orchestration/reporting, runtime bridge/delivery behavior, hosted runtime preflight/safety, the live GitHub read-only host bridge, durable-state schema design safety and runtime diagnostic semantics.

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
- the GitHub Actions live bridge can read required repository state and verify existing CI while failing closed if required workflows are missing and refusing write capabilities;
- the hosted-state SQL design is unapplied/rollback-only, owner-scoped, append-only for events and separate from keirin prediction tables;
- hosted runtime diagnostics never claim an unbound capability is authorized or verified.

## Current agent state

The project now has a tested generic runtime core, a real hosted Supabase preflight/diagnostic shell, one verified live external-tool binding through GitHub Actions, and a reviewed durable-state schema design. This is no longer only a design/library exercise, but it is still not an always-on self-contained AI agent.

Still missing for independent autonomous operation:

- activation of durable private task state; the design exists but database writes are intentionally not enabled;
- a secure runtime credential/permission store for provider bindings that require non-ephemeral authorization;
- a queue/worker scheduler that can resume tasks without an active chat or one-off workflow run;
- live bindings for Supabase/files/Web and later generation services;
- sales source/accounting rules/report destination;
- image/video/text-generation adapters and broader job routing.

Do not describe current ChatGPT/Work tool use, the preflight Edge Function, or the GitHub read-only smoke worker by itself as a completed always-on agent.

## Next action

Continue the shared agent foundation while preserving the keirin track in parallel.

Next implementation slice:

1. Keep the durable-state schema unapplied until database-writing activation is explicitly authorized. When authorized, convert the rollback-only design into a reviewed staging migration and run RLS/security/advisor checks before enabling hosted persistence.
2. Add another live **read-only** binding where authorization can be safely supplied by the host. Supabase project/function status is preferred, but do not copy ChatGPT/Work connector credentials into the repository or hosted runtime.
3. Implement the future atomic claim/lease adapter only after the durable-state activation boundary is resolved. The pure queue planner and worker design now exist; concurrency, fencing and crash-recovery integration tests remain required before any hosted activation.
4. Preserve the live GitHub worker as a read-only verification path so future repository/CI checks do not require screenshots.
5. Keep the 21:00 Asia/Tokyo report scheduler disabled until sales source, accounting rules and delivery destination are explicitly resolved.
6. Continue prospective keirin data collection when suitable races are available, but do not let it replace common agent-runtime development.

## Constraints

Keep production prediction, development DB writing for keirin prediction flows and external automatic race-data fetching OFF. Hosted agent persistence is also OFF until separately authorized. Scores remain uncalibrated; monetary EV and production promotion remain disabled. Do not commit private histories, snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current GitHub `main`, deployed function metadata and current tests to older handoff notes.

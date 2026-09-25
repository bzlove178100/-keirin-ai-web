# Work status

Updated: 2026-09-25 UTC.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is the authoritative shared goal. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI remains the first major execution target, not the only product scope.

## Keirin AI / prospective evaluation

Verified current state:

- Production prediction: **OFF**.
- Keirin development prediction DB writes: **OFF**.
- Automatic external keirin race-data fetching: **OFF**.
- Owner-only dry-run remains the validation path.
- Unknown odds are not invented.
- Probabilities remain uncalibrated for monetary EV / production promotion.
- First new prospective real-race history is 2026-09-24 Ito Onsen 1R: 7 riders, 210 model probabilities, 72 confirmed pre-race trifecta odds, valid pre-result chronology and supervised-training eligibility.
- Real prospective collection remains 1 eligible distinct prediction time. Four more distinct eligible times are required to reach the evaluator's five-time technical minimum; boundary purging can require more. Five is not evidence of accuracy or profitability.
- Two older history variants without `training_input` are not eligible for the current paired evaluation.

Relevant merged work includes offline LightGBM inference/evaluation, strict prospective capture and chronology, private history bundling, readiness UI and the unified strict chronological split protocol through PR #31.

## Shared autonomous-agent foundation

### Runtime core and recovery

Merged and verified:

- PR #32: broad autonomous-agent goal made authoritative.
- PR #33: machine-readable `TaskSpec`, local/private task state, activity ledger, allowed-action gates, idempotency keys, verification hooks and artifact lifecycle separation.
- PR #35: explicit reconciliation, capability/permission metadata, orchestration preflight, read-only GitHub adapter contract and Asia/Tokyo reporting contracts. Missing revenue remains `unknown/unavailable`, never silently zero.
- PR #37: credential-free runtime binding manifests, provider-neutral runtime bridge, read-only Supabase/file adapter contracts, CLI/runtime utilities, report-delivery separation and disabled-by-default 21:00 scheduling contract.
- PR #40: first live external provider path through a GitHub Actions read-only worker using ephemeral `GITHUB_TOKEN`; repository/CI verification works without screenshots and write capabilities are blocked.
- PR #45: pure owner-scoped queue planner / worker-lifecycle contract. It does not claim tasks or perform hosted I/O.
- PR #46: interruption safety prevents automatic repetition after an attempted-but-incomplete side effect and adds nonblocking local per-task locking.
- PR #47: task state is bound to an immutable fingerprint of the complete TaskSpec so a reused task ID with changed inputs/actions/permissions/retry rules cannot silently resume.
- PR #48: rollback-only hosted checkpoint v2 preparation with immutable task definition, revision CAS, owner-role grants, atomic checkpoint/audit writes and PostgreSQL 17 isolation tests.
- PR #49: broad capability contracts for public research, text/image/video/code generation, learning evaluation and report generation. These provider capabilities remain declared but unbound.
- PR #50: hosted runtime message cleanup plus `deno check` for the Edge Function entrypoint.
- PR #51: status refreshed before persistence activation.
- PR #52 (`ac4d529c72d91f992685c8bffc1af9363a65ec74`): authorized owner-only hosted agent checkpoint persistence, migration records, RLS/CAS safety tests, v4 checkpoint runtime contract and create/get/list/save endpoints. All PR CI workflows passed before merge.
- PR #53 (`4d9f29dfbb5184cc70d857a34cd21a6db7e852f6`): documentation aligned with the activated staging persistence state and explicit remaining verification boundaries.
- PR #54 (`cd8e87ff66c517f1eaaab6acdb94e13215a119e1`): strict provider-neutral `HostedCheckpointClient` for create/get/list/save. It recomputes the canonical Python TaskSpec fingerprint and fails closed on changed task definitions, corrupted fingerprints, invalid status/revision state or stale CAS writes. All PR workflows passed before merge.
- PR #56 (`94c98cb10cc7324dbcd16dae1cdb9f35ef7c4e45`): owner-only append/read activity persistence, strict provider-neutral `HostedActivityClient`, secret-shaped payload rejection and Edge runtime v5 activity modes. All PR CI workflows passed. Staging migration and v5 deployment were verified before merge.

### Hosted persistence activation

The user explicitly authorized **AI-agent-only task/activity persistence in staging**. That authorization does not extend to keirin prediction writes, production prediction, automatic race-data fetching, provider writes/generation, hosted task execution or report delivery.

Applied staging migrations in `keirin-ai-staging`:

- `20260925103650_agent_runtime_checkpoints_activation`
- `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
- `20260925115914_agent_runtime_activity_event_rpc`
- `20260925122122_agent_runtime_queue_lease`

Current agent storage:

- `public.agent_tasks`
- `public.agent_task_events`
- owner-derived `agent_create_checkpoint(...)`
- revision-CAS `agent_save_checkpoint(...)`
- owner-derived `agent_append_event(...)`
- queue coordination columns for not-before time, attempt budget, lease owner/generation/expiry
- atomic `agent_claim_next_task(...)` using `FOR UPDATE SKIP LOCKED`
- fenced `agent_save_leased_checkpoint(...)`
- explicit `agent_reconcile_expired_lease(...)` that blocks ambiguous expired work instead of silently retrying it
- owner-only RLS using `user_profiles(role='owner', plan='owner')`
- immutable task definition/fingerprint after creation
- completed-state protection
- append-only event access for authenticated owner role
- no authenticated task DELETE grant

Direct rollback tests in staging verified owner access, non-owner and anonymous denial, duplicate idempotency rejection, CAS success/stale-conflict behavior, completed-state immutability, append-only events, task DELETE denial and atomic checkpoint/event behavior. RPC tests also verified create/save behavior and `blocked_reason` / `last_error` synchronization. A staging event append/read round-trip was also verified after the activity migration.

The queue-lease implementation passed real PostgreSQL 17 CI coverage for atomic claiming, fencing, stale worker/revision rejection, attempt budgeting and explicit expired-lease reconciliation before staging migration application. The migration is applied; an always-on worker is still not activated.

The performance advisor no longer reports agent-table RLS init-plan warnings after the follow-up migration. The remaining `user_profiles_select_own` performance warning predates this activation. Security advisor findings remain unrelated existing items: `race_predictions` RLS has no policy, and leaked-password protection is disabled.

### Hosted runtime

`supabase/functions/agent-runtime-dev` is owner-only and protected with `verify_jwt=true`.

After PR #56 it was deployed as Supabase Edge Function **version 5**, status **ACTIVE**. The v5 service contract is `v5-owner-checkpoint-activity-persistence`.

The current queue-lease branch defines the next v6 contract with queue claim/save/reconcile endpoints while retaining `runtime_task_execution_enabled=false`. Deploy v6 only after current-branch CI is green and source/state alignment is confirmed.

Hosted persistence modes include checkpoint create/get/list/save plus activity append/list. Queue coordination is storage/lease control, not task execution.

Current safety state remains:

- agent checkpoint/activity persistence: **ON, agent-only**;
- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- external provider generation/write bindings: **unbound**;
- report delivery: **OFF / unconfigured**.

## Validation

CI currently covers:

- shared agent core safety;
- interrupted/competing runner cases;
- immutable task identity;
- orchestration/reporting;
- queue planning;
- runtime bridge/delivery;
- live GitHub read-only host bridge;
- broad capability contracts;
- activated hosted checkpoint/activity migration safety;
- strict hosted checkpoint/activity clients;
- queue lease/fencing migration safety and isolated PostgreSQL 17 crash/fencing tests;
- Web/prospective/ML regression;
- Phase32/training-input contracts;
- hosted runtime contract tests and entrypoint type-checking.

The design still separates `created`, `verified`, `persistent_saved`, `device_saved` and `ui_loaded` artifact states and does not treat Work/Chat execution as proof of an independent always-on agent.

## Current agent state

The project now has:

- a tested generic task/runtime core;
- safe resume/reconciliation semantics;
- a queue-planning contract;
- durable owner-only agent checkpoint/activity storage active in staging;
- queue lease/fencing schema active in staging, without an active worker;
- a hosted Supabase persistence/preflight shell;
- strict hosted checkpoint/activity clients;
- a verified live GitHub read-only provider path;
- broad capability contracts for research/text/image/video/code/learning/report generation.

It is still **not** an always-on self-contained autonomous agent.

Major remaining gaps:

1. queue lease/fencing must be exposed and verified through the deployed v6 hosted runtime before wiring a distributed worker;
2. `AgentRunner` is not yet wired to hosted checkpoint/activity/queue state;
3. no always-on worker or scheduler host is activated;
4. Supabase/files/Web/model-provider live bindings are not yet broadly connected;
5. text/image/video/code capabilities are declared but provider-unbound;
6. sales source, accounting rules and report destination are unresolved;
7. 21:00 report generation/delivery is not scheduled live.

## Next action

Continue without asking for race screenshots unless a race-data step genuinely requires user input.

Next safe implementation slice:

1. deploy and verify hosted runtime v6 for queue claim/save/reconcile while task execution stays disabled;
2. add a strict hosted worker coordinator that composes queue claim + preflight + checkpoint/activity clients but does not yet invoke write/execute provider actions;
3. test crash recovery and stale-worker fencing through the hosted transport;
4. wire a read-only first worker task (repository/CI status) only after the coordinator proves fail-closed behavior;
5. keep provider generation bindings and report delivery as separate authorization/configuration steps.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of:

- daily sales;
- monthly sales;
- activity report: work executed, results, failures/incomplete work and next actions.

Sales source, accounting rules and delivery destination are still unresolved. Missing sales values must not be shown as zero. Report delivery/scheduling stays disabled until those inputs are defined.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

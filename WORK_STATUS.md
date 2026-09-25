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

Verified implementation history:

- PR #32 made the broad autonomous-agent goal authoritative.
- PR #33 added machine-readable `TaskSpec`, local/private task state, activity ledger, allowed-action gates, idempotency keys, verification hooks and artifact lifecycle separation.
- PR #35 added explicit reconciliation, capability/permission metadata, orchestration preflight, read-only GitHub adapter contracts and Asia/Tokyo reporting contracts. Missing revenue remains `unknown/unavailable`, never silently zero.
- PR #37 added credential-free runtime binding manifests, a provider-neutral runtime bridge, read-only Supabase/file adapter contracts, CLI/runtime utilities, report-delivery separation and a disabled-by-default 21:00 scheduling contract.
- PR #40 added the first live external provider path through a GitHub Actions read-only worker using ephemeral `GITHUB_TOKEN`; repository/CI verification works without screenshots and write capabilities are blocked.
- PR #45 added the pure owner-scoped queue planner / worker-lifecycle contract.
- PR #46 added interruption safety and nonblocking local per-task locking.
- PR #47 bound durable state to the immutable fingerprint of the complete TaskSpec.
- PR #48 prepared rollback-only hosted checkpoint v2 with PostgreSQL 17 isolation tests.
- PR #49 declared broad public-research/text/image/video/code/learning/report capabilities while leaving providers unbound.
- PR #52 activated authorized owner-only hosted checkpoint persistence in staging.
- PR #54 added the strict provider-neutral `HostedCheckpointClient`.
- PR #56 (`94c98cb10cc7324dbcd16dae1cdb9f35ef7c4e45`) added owner-only append/read activity persistence and `HostedActivityClient`; all PR workflows passed and runtime v5 was deployed before merge.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`) added crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL 17 fencing tests. All PR workflows passed before merge.
- PR #58 adds a fail-closed `HostedWorkerCoordinator` that composes queue claim, ToolRegistry preflight and activity logging without invoking provider actions. Every inspected claim is durably released as blocked while hosted task execution remains unactivated.

### Hosted persistence activation

The user explicitly authorized **AI-agent-only task/activity persistence in staging**. That authorization does not extend to keirin prediction writes, production prediction, automatic race-data fetching, provider writes/generation, hosted task execution or report delivery.

Applied staging migrations in `keirin-ai-staging`:

- `20260925103650_agent_runtime_checkpoints_activation`
- `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
- `20260925115914_agent_runtime_activity_event_rpc`
- `20260925122122_agent_runtime_queue_lease`

Current agent storage and coordination:

- `public.agent_tasks`
- `public.agent_task_events`
- owner-derived checkpoint create/save RPCs with revision CAS
- owner-derived activity append RPC
- queue metadata for not-before time, attempt budget, lease owner/generation/expiry
- atomic FIFO `agent_claim_next_task(...)` using `FOR UPDATE SKIP LOCKED`
- fenced `agent_save_leased_checkpoint(...)`
- explicit `agent_reconcile_expired_lease(...)` that blocks ambiguous expired work instead of silently retrying it
- owner-only RLS using `user_profiles(role='owner', plan='owner')`
- immutable task definition/fingerprint after creation
- completed-state protection
- append-only event access for authenticated owner role
- no authenticated task DELETE grant

Staging verification confirms all six queue metadata columns and all three queue RPCs exist. `race_predictions` remains at zero rows. The queue schema is active, but no always-on worker is activated.

Security advisor findings remain unrelated existing items: `race_predictions` has RLS enabled with no policy, and leaked-password protection is disabled. The performance advisor still reports the pre-existing `user_profiles_select_own` auth init-plan warning. Newly created queue indexes may appear as unused before worker load; that is not treated as proof they should be removed.

### Hosted runtime

`supabase/functions/agent-runtime-dev` is owner-only and protected with `verify_jwt=true`.

After PR #57, the function was deployed and read back as **version 6 / ACTIVE**, with service contract `v6-owner-queue-lease-fencing`.

Hosted modes include:

- checkpoint create/get/list/save;
- activity append/list;
- queue claim/save/reconcile-expired.

The deployed source verifies queue RPC results by reading durable state back before returning success. Queue responses still report `executed:false` and the runtime safety contract keeps `runtime_task_execution_enabled=false`.

Current safety state:

- agent checkpoint/activity persistence: **ON, agent-only**;
- queue coordination: **ON, agent-only**;
- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- external provider generation/write bindings: **unbound**;
- report delivery: **OFF / unconfigured**.

A real request through the deployed Edge Function using the user's browser owner JWT has not yet been performed in this chat; do not mark that browser-to-Edge path verified until it is actually tested.

## Validation

CI covers shared agent core safety, interrupted/competing runner behavior, immutable task identity, orchestration/reporting, queue planning, runtime bridge/delivery, live GitHub read-only host bridge, broad capability contracts, hosted checkpoint/activity/queue clients, migration safety, isolated PostgreSQL 17 queue fencing/crash cases, Web/prospective/ML regression, Phase32/training-input contracts and hosted runtime type/contract checks.

PR #58 additionally tests that the hosted worker coordinator never invokes provider actions, fails closed on missing or forbidden capabilities, releases an inspected lease as blocked, and does not report release success when durable queue save fails.

The design still separates `created`, `verified`, `persistent_saved`, `device_saved` and `ui_loaded` artifact states and does not treat Work/Chat execution as proof of an independent always-on agent.

## Current agent state

The project now has a tested generic task/runtime core, safe resume/reconciliation semantics, durable owner-only checkpoint/activity storage, crash-safe queue lease/fencing, strict hosted persistence clients, a deployed v6 coordination runtime, a verified live GitHub read-only provider path and broad provider-neutral capability contracts.

It is still **not** an always-on self-contained autonomous agent. The current worker coordinator is intentionally non-executing.

Major remaining gaps:

1. prove the fail-closed hosted worker coordinator through CI and merge it;
2. test one real authenticated owner browser-to-Edge persistence/queue flow when an owner session is available, without storing the token;
3. design the explicit execution-host activation boundary before wiring `AgentRunner` or provider actions to claimed leases;
4. connect additional safe read-only Supabase/files/Web bindings where host authorization exists;
5. text/image/video/code capabilities remain provider-unbound;
6. sales source, accounting rules and report destination remain unresolved;
7. 21:00 report generation/delivery is not scheduled live.

## Next action

Continue without asking for race screenshots unless a race-data step genuinely requires user input.

After the fail-closed coordinator is merged, prepare a read-only first-worker execution design around repository/CI status. Do not activate hosted task execution, an always-on scheduler, provider generation/write bindings or report delivery without the corresponding explicit authorization/configuration step.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and the activity report (work executed, results, failures/incomplete work and next actions).

Sales source, accounting rules and delivery destination are still unresolved. Missing sales values must not be shown as zero. Report delivery/scheduling stays disabled until those inputs are defined.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

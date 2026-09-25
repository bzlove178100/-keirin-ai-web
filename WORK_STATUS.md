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

## Shared autonomous-agent foundation

Key merged milestones:

- PR #32: broad autonomous-agent goal made authoritative.
- PR #33: `TaskSpec`, durable task-state model, activity ledger, allowed-action gates, idempotency keys, verification hooks and artifact lifecycle separation.
- PR #35: explicit reconciliation, capability/permission metadata, orchestration preflight, read-only GitHub adapter contract and Asia/Tokyo reporting contracts. Missing revenue stays `unknown/unavailable`, never silently zero.
- PR #37: credential-free runtime binding manifests, provider-neutral bridge, read-only Supabase/file adapter contracts, CLI/runtime utilities and report-delivery separation.
- PR #40: verified live GitHub read-only provider path using ephemeral GitHub Actions credentials.
- PR #45–#47: queue planning, interruption safety, local task locking and immutable full-TaskSpec fingerprint binding.
- PR #52: authorized owner-only hosted checkpoint persistence in staging.
- PR #54: strict provider-neutral `HostedCheckpointClient`.
- PR #56 (`94c98cb10cc7324dbcd16dae1cdb9f35ef7c4e45`): owner-only append/read activity persistence and strict `HostedActivityClient`.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL 17 fencing tests.
- PR #58 (`e21dca79a08e21b12979cf886fceaf3c69c33763`): fail-closed `HostedWorkerCoordinator`; queue claims can be preflighted and durably released as blocked without invoking provider actions.
- PR #59 prepares an explicitly gated `HostedReadOnlyWorker` and `HostedLeaseStateStore`. The default is execution denied before queue claim. When enabled only in an explicitly authorized host, all task actions/verifiers must be registered `read` capabilities and every AgentRunner state transition is persisted through queue revision-CAS/fencing. CI tests use fake/injected actions only; this is preparation, not live activation.

## Hosted persistence and queue state

The user explicitly authorized **AI-agent-only task/activity persistence in staging**. That authorization does not extend to keirin prediction writes, production prediction, automatic race-data fetching, provider writes/generation, hosted task execution or report delivery.

Applied `keirin-ai-staging` migrations:

- `20260925103650_agent_runtime_checkpoints_activation`
- `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
- `20260925115914_agent_runtime_activity_event_rpc`
- `20260925122122_agent_runtime_queue_lease`

Verified storage/coordination:

- `public.agent_tasks` and `public.agent_task_events` are owner-scoped through RLS.
- Checkpoint create/save uses immutable TaskSpec identity plus revision CAS.
- Activity events are append-only for the owner path.
- Queue metadata tracks not-before time, attempt budget, lease owner/generation/expiry.
- `agent_claim_next_task(...)` uses atomic FIFO `FOR UPDATE SKIP LOCKED`.
- `agent_save_leased_checkpoint(...)` rejects stale revision/worker/generation and expired leases.
- `agent_reconcile_expired_lease(...)` blocks ambiguous expired work instead of silently retrying/requeueing it.
- Staging exposes all six queue metadata columns and all three queue RPCs.
- `race_predictions` remains at **0 rows**.
- No always-on worker is active.

Security advisor findings remain existing/unrelated items: `race_predictions` has RLS with no policy, and leaked-password protection is disabled. The performance advisor still reports the pre-existing `user_profiles_select_own` auth init-plan warning. Newly created queue indexes may appear unused before worker load; that is not evidence they should be removed.

## Hosted runtime

`supabase/functions/agent-runtime-dev` is owner-only and uses `verify_jwt=true`.

Current deployed/read-back state:

- Edge Function: **version 6 / ACTIVE**.
- Service contract: `v6-owner-queue-lease-fencing`.
- Checkpoint modes: create/get/list/save.
- Activity modes: append/list.
- Queue modes: claim/save/reconcile-expired.
- Queue RPC responses are read back from durable state before success is returned.
- Queue responses still report `executed:false`.

Safety state remains:

- agent checkpoint/activity persistence: **ON, agent-only**;
- queue coordination: **ON, agent-only**;
- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- external provider generation/write bindings: **unbound**;
- report delivery: **OFF / unconfigured**.

A real browser-owner-JWT request through the deployed Edge Function has not yet been performed in this chat. Do not mark that specific browser-to-Edge path verified until it is actually tested.

## Validation

CI covers shared agent safety/recovery, immutable task identity, orchestration/reporting, queue planning, hosted checkpoint/activity/queue clients, migration safety, PostgreSQL 17 queue fencing/crash cases, runtime bridge/delivery, live GitHub read-only host behavior, Web/prospective/ML regression, Phase32/training-input contracts and hosted runtime type/contract checks.

PR #58 added tests proving the coordinator never executes provider actions and fails closed on missing/forbidden capabilities or persistence failures.

PR #59 adds tests proving:

- hosted read-only execution is denied **before queue claim** unless explicitly authorized by the host;
- authorized fake read-only action + verifier can complete through durable fenced state transitions;
- write/execute or missing actions are blocked without invocation;
- a read-only adapter cannot silently report artifact creation/persistent/device/UI writes as success.

## Current agent state

The project has a tested generic task/runtime core, safe resume/reconciliation, durable owner-only checkpoint/activity storage, crash-safe queue lease/fencing, strict hosted persistence clients, deployed v6 coordination runtime, a verified GitHub read-only provider path, a fail-closed worker coordinator and broad provider-neutral capability contracts.

It is still **not** an always-on self-contained autonomous agent. `agent-runtime-dev` does not execute tasks, and no scheduler/worker service is active.

Remaining major boundaries:

1. merge the explicitly gated read-only worker preparation after CI;
2. separately authorize and configure any live hosted task execution before setting an execution host to enabled;
3. test a real authenticated owner browser-to-Edge flow without storing the user's token;
4. connect additional safe read-only Supabase/files/Web provider bindings where host authorization exists;
5. text/image/video/code generation providers remain unbound;
6. sales source, accounting rules and report destination are unresolved;
7. 21:00 report generation/delivery remains unscheduled.

## Next action

After PR #59 is merged, the next implementation step is to prepare the concrete **read-only repository/CI status task binding** and host activation checklist. Keep the live execution flag OFF until the user explicitly authorizes hosted task execution. Do not ask for race screenshots unless a race-data step genuinely requires user input.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and an activity report covering executed work, results, failures/incomplete work and next actions.

Sales source, accounting rules and delivery destination are still unresolved. Missing sales values must not be shown as zero. Report delivery/scheduling stays disabled until those inputs are defined.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

# Hosted agent state design

Status: **agent-only checkpoint persistence active in staging**

The original rollback-only designs remain archived at:

- `supabase/schema/agent_runtime_state_v1.sql`
- `supabase/schema/agent_runtime_checkpoints_v2.sql`

They are still intentionally non-deployable reference designs. The authorized staging activation is now recorded separately under `supabase/migrations`.

## Activated scope

On 2026-09-25 the user explicitly authorized AI-agent-only task/activity persistence in `keirin-ai-staging`. The activation does **not** authorize keirin prediction DB writes, production prediction, automatic external race-data fetching, provider writes/generation, hosted task execution, report delivery, or the 21:00 schedule.

Applied staging migrations:

1. `20260925103650_agent_runtime_checkpoints_activation`
   - creates `public.agent_tasks` and `public.agent_task_events`;
   - owner-scoped RLS through `user_profiles(role='owner', plan='owner')`;
   - immutable task identity and `spec_fingerprint`;
   - monotonic `revision`;
   - compare-and-swap `agent_save_checkpoint`;
   - automatic `checkpoint_saved` audit events;
   - completed-state mutation protection;
   - no authenticated DELETE grant for tasks and no UPDATE/DELETE grant for event rows.
2. `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
   - adds owner-derived `agent_create_checkpoint` so callers do not supply a user ID;
   - preserves SECURITY INVOKER semantics;
   - synchronizes `blocked_reason` and `last_error` during checkpoint saves;
   - rewrites agent RLS predicates to `(select auth.uid())` to avoid per-row auth-function re-evaluation.

These migrations operate only on agent task/activity state. They do not write `race_predictions`, prospective race histories, model artifacts, settlement data, or `user_profiles`.

## Current hosted runtime

`supabase/functions/agent-runtime-dev` is now the owner-only hosted checkpoint shell. Its service contract is `v4-owner-checkpoint-persistence`, deployed as Supabase Edge Function version 4 with `verify_jwt=true` and ACTIVE status.

Available hosted modes:

- `preflight`
- `checkpoint_create`
- `checkpoint_get`
- `checkpoint_list`
- `checkpoint_save`

The runtime still reports:

- production prediction: OFF;
- keirin prediction DB writing: OFF;
- automatic external keirin race-data fetching: OFF;
- hosted task execution: OFF;
- checkpoint persistence scope: `agent_only`;
- external provider generation/write bindings: unbound;
- report delivery: disabled/unconfigured.

The checkpoint routes reuse the authenticated owner JWT and the project's publishable/anon key so PostgreSQL RLS remains the authorization boundary. No service-role bypass is part of the runtime path.

## Verified database properties

Direct staging validation has confirmed:

- RLS enabled on both agent tables;
- owner can create and update own checkpoint state;
- duplicate per-owner idempotency keys are rejected;
- compare-and-swap revision updates succeed only with the expected revision;
- stale revisions fail;
- completed checkpoints cannot be mutated;
- event rows cannot be updated by the authenticated owner role;
- task deletion is denied to the authenticated owner role;
- a different authenticated user cannot read the owner's task or insert agent state;
- anonymous table access is denied;
- checkpoint writes and their audit events are atomic;
- create/save RPC behavior and `blocked_reason` / `last_error` synchronization work in rollback tests.

The self-tests used temporary rows inside transactions and rolled them back. They did not leave test task/event data behind.

## Advisor state

After the agent RLS optimization, Supabase's performance advisor no longer reports init-plan warnings for the agent tables. An existing warning remains for `public.user_profiles.user_profiles_select_own`; that is outside this activation.

Security advisor findings are also pre-existing/non-agent-specific: `race_predictions` has RLS enabled with no policies, and leaked-password protection is disabled. The agent persistence activation did not introduce a new security-advisor finding.

## Task state contract

A hosted task stores:

- stable `task_id`;
- schema version;
- status: `queued`, `running`, `blocked`, `completed`, `failed`;
- stable per-owner idempotency key;
- immutable TaskSpec JSON;
- current runtime state JSON;
- immutable TaskSpec fingerprint;
- monotonic revision;
- block/error information;
- create/update timestamps.

`(user_id, task_id)` is the primary key and `(user_id, idempotency_key)` is unique.

`agent_save_checkpoint` is a checkpoint operation, not a queue claim or worker authorization. It does not create leases, worker fencing, provider authorization, or a scheduler. Those remain separate future gates.

The supplied `sha256-v1` fingerprint is format-checked and immutable in PostgreSQL; SQL does not recompute Python's canonical TaskSpec fingerprint. A future host adapter must recompute/verify the canonical fingerprint when binding stored state back to TaskSpec execution.

## Activity ledger

`agent_task_events` is append-only for the authenticated owner role. Checkpoint triggers append `checkpoint_saved` in the same transaction as the task-state write. This is an operational audit/recovery ledger, not a cryptographically tamper-proof audit log.

## Remaining verification boundary

The database/RLS/RPC path has been validated directly and the v4 Edge Function source passed repository regression/type-checking before merge and was read back ACTIVE after deployment.

An authenticated end-to-end call through the deployed Edge Function using the user's real browser owner session has **not** yet been executed in this chat. Do not describe that specific browser-to-Edge path as verified until such a call is made.

## Next architecture step

The next safe implementation work is to connect the shared agent runtime/store abstraction to these hosted checkpoint endpoints while task execution remains OFF. After that, add queue claim/lease/fencing and crash-recovery integration tests before considering any always-on worker activation.

Provider bindings, text/image/video/code generation, report delivery, and the 21:00 schedule remain independent authorization/configuration steps.

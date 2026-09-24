# Hosted agent state design v1

Status: **design only / not deployed**

The shared agent can currently persist state locally inside a host process, and the live GitHub Actions worker proves one read-only provider binding. The hosted Supabase `agent-runtime-dev` shell remains preflight-only. The next architectural requirement is durable private task state so work can survive a chat, browser, or one-off runner ending.

This document defines that state contract without enabling database writes.

## Why this is separate from the keirin prediction database

Durable agent state is operational control data, not race prediction output. It must not be mixed into `race_predictions`, prospective race history, model artifacts, or settlement data. The draft uses dedicated tables:

- `public.agent_tasks` — one current durable state per user/task ID.
- `public.agent_task_events` — append-only activity/recovery ledger.

The executable SQL draft is `supabase/schema/agent_runtime_state_v1.sql`. It is deliberately outside `supabase/migrations` and wraps all DDL in `BEGIN ... ROLLBACK`, so it is not a deployment migration.

## Task state

A hosted task stores:

- stable `task_id`;
- schema version;
- queue status: `queued`, `running`, `blocked`, `completed`, `failed`;
- stable idempotency key;
- immutable task specification JSON;
- current runtime state JSON;
- block/error information;
- create/update timestamps.

The `(user_id, task_id)` pair is the primary key. `(user_id, idempotency_key)` is unique. This prevents a second logical task from silently reusing the same idempotency key for the same user.

## Activity ledger

`agent_task_events` is append-only by policy in v1. It records event type, optional step ID, structured payload and timestamp. No UPDATE or DELETE RLS policy is defined for event rows. This keeps a trace of retries, blocks, reconciliation and completion rather than rewriting history.

## Access model

The draft enables RLS on both tables and limits direct authenticated access to:

1. rows whose `user_id = auth.uid()`; and
2. a matching `user_profiles` row with `role=owner` and `plan=owner`.

No service-role bypass, secret, token, password or credential is included in the schema design. A future hosted runtime write path must continue to verify owner authorization before writing.

## Activation boundary

The schema is **not active** and `agent-runtime-dev` must keep:

- `runtime_task_execution_enabled=false`;
- `persistence_enabled=false`;
- production prediction OFF;
- keirin prediction DB writes OFF;
- external automatic race-data fetching OFF.

Before activation, create a real migration from the draft, review it, run it against the staging project, inspect RLS/security advisors, and add end-to-end tests proving one owner can only read/write their own task state. That activation changes the current no-write runtime behavior and therefore is intentionally left for a separate explicit authorization.

## First activation test plan

When authorized later:

1. Apply only the dedicated agent-state migration to staging.
2. Confirm `agent_tasks` and `agent_task_events` have RLS enabled.
3. Confirm an unauthenticated client cannot read or write them.
4. Confirm a non-owner authenticated profile cannot read or write them.
5. Confirm the owner can create one queued task with a stable idempotency key.
6. Attempt the same idempotency key twice and verify the second insert is rejected.
7. Append an event, then verify direct UPDATE/DELETE of that event is rejected.
8. Resume the task from the hosted runtime and verify already completed steps are not repeated.
9. Run Supabase security/performance advisors.
10. Only after all checks pass, consider enabling hosted persistence; task execution and provider writes remain separate gates.

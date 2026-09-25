# Hosted agent state design v1

Status: **design only / not deployed**

## Checkpoint implementation prepared (v2)

`supabase/schema/agent_runtime_checkpoints_v2.sql` extends the v1 design. Both
remain rollback-only and outside migrations. v2 adds immutable task identity,
monotonic revisions, a compare-and-swap checkpoint function, explicit grants and
an audit trigger in the same transaction as every state write. The function uses
SECURITY INVOKER and auth.uid(); existing owner RLS still applies. No credentials
or real user/race data are part of the files.

`agent_save_checkpoint` is a state-saving operation, not a task claim or worker
authorization. It does not provide leases, worker fencing, provider bindings or a
scheduler. Authenticated owners have direct table writes subject to RLS/triggers;
the trusted host must enforce TaskSpec validity, transitions and reconciliation.
The supplied fingerprint is format-checked and immutable, not recomputed in SQL;
the full stored specification is also immutable. The host computes/verifies the
Python canonical fingerprint before binding a task to execution.

The ledger is append-only for the authenticated role; it is not a cryptographic
audit trail and direct authorized inserts are possible. A checkpoint write that
cannot append its event fails atomically. Deletes are not granted. Completed
checkpoints cannot be overwritten. Neither schema is a migration for existing
tasks; the current staging project was checked and has neither agent table.

The PostgreSQL 17 CI service uses only synthetic owners and data in a rollback
transaction. It tests owner isolation, non-owner/anonymous denial, duplicate
identity rejection, immutable definitions, stale revisions, append-only events,
audit failure rollback and completed-state protection. It does not validate the
actual Supabase JWT gateway, deployed profile policies, concurrent worker claims
or end-to-end hosted resume. Deployment/advisor checks are still required later.

Activation scope for a later explicit authorization: create only the dedicated
agent task/event storage and checkpoint function in staging after converting the
reviewed designs into a migration. Do not enable prediction writes, task execution,
external race fetching or the 21:00 schedule. The activation process must verify
current profile authorization/grants, RLS and security advisors before connecting
the owner-only hosted shell to persistence.

Sources checked for v2: Supabase database functions and RLS documentation:
https://supabase.com/docs/guides/database/functions
https://supabase.com/docs/guides/database/postgres/row-level-security

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

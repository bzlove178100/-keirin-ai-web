# Hosted read-only execution activation checklist

This document defines the boundary between **prepared code** and **live hosted task execution**.

The current deployed `agent-runtime-dev` safety contract keeps `runtime_task_execution_enabled=false`. Merging code that implements this checklist does not activate a worker, scheduler or provider execution.

## First live scope

The first hosted execution scope must be limited to the existing repository/CI status task:

- task: `agent_core/examples/keirin_readonly_status_task.json`
- repository: `bzlove178100/-keirin-ai-web`
- allowed capabilities:
  - `github.read_main`
  - `github.verify_ci`
- allowed access class: `read` only
- GitHub writes: forbidden
- Supabase prediction writes: forbidden
- production prediction: forbidden
- automatic external keirin race-data fetching: forbidden
- generation providers: unbound
- report delivery: disabled

## Required authorization before activation

Do not set a live host's `HostedReadOnlyWorker(execution_authorized=True)` merely because this code exists.

Before live activation, all of the following must be true:

1. The user explicitly authorizes hosted **read-only task execution** as a separate boundary from persistence/queue coordination.
2. The deployed Edge Function is read back as the expected version and still reports hosted task execution OFF at the Edge layer; the execution host itself owns the separate read-only authorization gate.
3. The host has a valid owner-authenticated Supabase access token and a publishable key through runtime secret storage or ephemeral environment injection. Credentials are not written to TaskSpec, task state, activity events, artifacts, logs or this repository.
4. The GitHub provider binding exposes only `contents:read` and `actions:read` behavior for the first task.
5. The TaskSpec fingerprint is verified before resume/execution.
6. Queue claim uses revision CAS plus worker/generation fencing, and the host stops on stale/expired lease errors.
7. Only one first-worker process is enabled during the initial live validation.
8. No recurring scheduler is enabled during the first validation.

## Credential boundary

`agent_core.hosted_transport.SupabaseEdgeTransport` accepts a project URL, publishable key and owner bearer token at runtime. The credentials live only in the host process and HTTP headers.

Do not:

- commit access/refresh tokens;
- put tokens in TaskSpec inputs;
- put tokens in queue/activity payloads;
- use a browser-exposed service-role/secret key;
- copy an owner token into CI logs or artifacts;
- treat the transport as a token refresh/session manager.

Long-lived unattended execution will require a separately designed authentication/session lifecycle and secret-management policy. That is not solved by the transport class alone.

## First validation sequence

After explicit authorization:

1. Verify the owner-authenticated Edge path using a non-destructive status/list request.
2. Create or select one dedicated test checkpoint for `keirin_readonly_status_task.json`.
3. Claim exactly one task with a short bounded lease.
4. Re-run capability preflight after claim.
5. Execute only the two read-only GitHub capabilities.
6. Persist every AgentRunner state transition through the fenced hosted lease store.
7. Verify final task status is `completed`, the lease is cleared, and activity events show the expected start/step/verify/completion sequence.
8. Verify `race_predictions` remains unchanged and all production/auto-fetch safety flags remain OFF.
9. Stop. Do not enable recurrence until the single-run evidence is reviewed.

## Fail-closed / rollback behavior

If any authorization, preflight, queue fence, provider read or verification check fails:

- do not downgrade the permission requirement;
- do not switch to a write-capable provider;
- do not silently retry an ambiguous interrupted action;
- preserve or reconcile durable state according to the existing queue/recovery contract;
- keep live execution authorization disabled for the next run until the failure is understood.

Rollback of the execution host is simply to stop the host and return `execution_authorized` to false. Queue/persistence data may remain for audit and reconciliation; do not delete it as a substitute for recovery.

## Not part of this activation

The following require their own later design/authorization:

- always-on/background scheduling;
- write-capable GitHub operations;
- Supabase application-data writes beyond the already-authorized agent state;
- automatic keirin race-data collection;
- text/image/video/code provider execution;
- sales ingestion;
- 21:00 report delivery.

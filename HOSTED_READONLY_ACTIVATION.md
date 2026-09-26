# Hosted read-only execution activation checklist

This document defines the boundary between **prepared code** and **live hosted task execution**.

The current deployed `agent-runtime-dev` safety contract keeps `runtime_task_execution_enabled=false`. Merging code that implements this checklist does not activate a worker, scheduler or provider execution.

## First live scope

The first hosted execution scope must be limited to the repository/CI status task:

- task template: `agent_core/examples/keirin_readonly_status_task.json`
- runtime instance: one fresh `keirin-readonly-status-check.<token>` TaskSpec only
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

Do not set a live host's read-only execution gate merely because this code exists.

Before live activation, all of the following must be true:

1. The user explicitly authorizes one hosted **read-only task execution** as a separate boundary from persistence/queue coordination.
2. That authorization is bound to exactly one fresh instance token. The host must receive both:
   - `KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED=true`
   - `KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN=<the exact --instance-token value>`
   A generic boolean authorization is insufficient by itself.
3. The deployed Edge functions are read back as the expected versions and still report provider/task execution disabled at the Edge layer; the external host owns the separate one-shot read-only authorization gate.
4. The host has a valid owner-authenticated Supabase access token and publishable key through runtime secret storage or ephemeral environment injection. Credentials are not written to TaskSpec, task state, activity events, artifacts, logs or this repository.
5. The GitHub provider binding exposes only `contents:read` and `actions:read` behavior for this task.
6. The TaskSpec fingerprint is verified before enqueue/resume/execution.
7. The host creates or verifies the exact pristine queued checkpoint before worker construction. Database persistence permits at most one fresh trusted status-run row in `queued` or `running` per owner.
8. Queue acquisition is exact-task only, with revision CAS plus worker/generation fencing. The host stops on stale/expired lease errors.
9. Only one manual host process is enabled during the initial validation.
10. No recurring scheduler is enabled.

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

## Manual one-shot sequence

The standalone entrypoint is `tools/run_hosted_repository_once.py`. It is still a manual one-shot host, not a scheduler.

After explicit authorization for one fresh instance:

1. Validate the closed committed activation manifest.
2. Build and validate the exact trusted TaskSpec from `--instance-token`.
3. Verify `KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN` exactly matches that token before loading runtime secrets or creating queue/provider objects.
4. Create or verify exactly that pristine queued checkpoint through `TrustedRunEnqueuer`.
5. If another distinct trusted run is already queued/running, fail closed before worker construction or claim.
6. Construct a worker permanently bound to the same TaskSpec.
7. Claim exactly that task through `agent-exact-claim-dev` with a short bounded lease.
8. Execute only the two read-only GitHub capabilities.
9. Persist every AgentRunner state transition through the fenced hosted lease store.
10. Inspect recovery/final state for the same TaskSpec even after interruption; never switch to another task identity.
11. Verify final task status, cleared lease, append-only evidence, and `race_predictions` unchanged.
12. Stop. The authorization is consumed for that instance. A different instance token requires a new explicit authorization value.

## Fail-closed / rollback behavior

If any authorization, enqueue, preflight, queue fence, provider read or verification check fails:

- do not downgrade the permission requirement;
- do not switch to a write-capable provider;
- do not create a second distinct trusted run while another is queued/running;
- do not silently retry an ambiguous interrupted action;
- preserve or reconcile durable state according to the existing queue/recovery contract;
- keep live execution authorization disabled for the next run until the failure is understood.

Rollback of the execution host is simply to stop the host and remove/disable the runtime authorization inputs. Queue/persistence data may remain for audit and reconciliation; do not delete it as a substitute for recovery.

## Not part of this activation

The following require their own later design/authorization:

- always-on/background scheduling;
- write-capable GitHub operations;
- Supabase application-data writes beyond the already-authorized agent state;
- automatic keirin race-data collection;
- text/image/video/code provider execution;
- sales ingestion;
- 21:00 report delivery.

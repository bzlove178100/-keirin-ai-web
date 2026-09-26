# Hosted repository/CI status binding design

Status: preparation only, 2026-09-26. No live execution authorization, workflow, scheduler, credentials or provider permissions are created by this document.

## Fixed first-task scope

Use `agent_core/examples/keirin_readonly_status_task.json` for `bzlove178100/-keirin-ai-web` only. Register exactly `github.read_main` (`contents:read`) and `github.verify_ci` (`actions:read`), both with access `read`. Agent checkpoint/activity/queue persistence is already separately authorized; application prediction writes remain forbidden.

The host must compare the entire claimed TaskSpec fingerprint against its trusted reviewed template, including inputs, required files, action/verifier, retry policy and completion conditions. Matching a task ID or two capability names alone is insufficient. Do not accept a queued task's repository, ref, permission declaration or execution flag as host authorization.

## Composition to implement

| Component | Binding and responsibility |
| --- | --- |
| SupabaseEdgeTransport | One runtime-only project URL, publishable key and owner JWT; no token serialization or refresh implementation. No redirect or automatic POST retry. |
| HostedQueueClient | Use the shared transport for claim/save/reconcile; validate durable task identity, revision and lease fencing. |
| HostedActivityClient | Use the same transport for sanitized append/list; persist only non-secret evidence. |
| GitHubReadOnlyBridge | Runtime-only GitHub credential; repository and SHA constrained by host policy. Never expose write operations. |
| BridgeToolAdapter / ToolRegistry | Build only the two capabilities from the existing `runtime_manifest()` in `tools/agent_github_readonly_host.py`. Do not use `BoundRuntime`'s local FileStateStore for hosted execution. |
| HostedReadOnlyWorker | Default `execution_authorized=False`; stop before queue claim unless separately explicitly authorized. Add a trusted-spec scope check after claim and before any provider action. |
| HostedLeaseStateStore | Existing AgentRunner persistence through queue revision CAS, worker ID and generation fencing; no local lock presented as a distributed lock. |

No new CLI or workflow should infer authorization from the presence of credentials, an environment string such as `"false"`, or task JSON. Any future activation input must be an explicit host-owned boolean, separate from task data. Keep the Edge runtime's execution flag false: the future external host is a different execution boundary.

## Findings that must be fixed before live binding

The existing GitHub bridge is a useful read-only foundation, but it is not yet sufficient evidence for a same-commit hosted status check:

1. `_read_main` fetches each file using a moving ref; resolve `main` to one full commit SHA first, then read every required file at that SHA. Reject missing/empty/non-decodable content and missing blob identity.
2. `_verify_ci` currently selects completed runs by workflow name on `main`; that can pick an older successful run while the current commit is failing or still running. Query the captured SHA without filtering out in-progress runs, pin the expected workflow identities, paginate as needed, and select the latest attempt. Missing, pending, cancelled, skipped or failed required runs must not yield success.
3. Re-read `main` before returning a current-main success. If it moved, report `main_changed` and retain the observed SHA; do not label a mixed observation current. New observation is an explicit later read-only attempt.
4. Preserve the observed SHA and minimal file/CI evidence through existing durable task state so verification after interruption cannot silently substitute a different commit.
5. Add exact template/repository scope validation after claim. The generic worker currently validates read access, not an exact first-task allowlist. An unexpected claim must be durably blocked/released without invoking GitHub, and the first-run host must then stop.
6. Harden the GitHub bridge's HTTP boundary before composition: reject redirects, sanitize exceptions/error bodies, and prevent credentials from reaching durable last_error/activity. The existing bridge currently includes a raw HTTP error body in its exception.
7. Define a bounded per-request and whole-step timeout relative to remaining lease time. Stop on stale/expired fences; a 120-second lease is not evidence that multiple 20-second requests plus persistence are safe. Renewal must use the existing fenced save contract, never silently reclaim the task.

The first required CI policy should explicitly cover `keirin-ai regression`, `collection progress UI regression`, `agent checkpoint PostgreSQL contract`, and `agent runtime read-only smoke`, using reviewed workflow identities at the observed SHA. The status task must not be part of a workflow that waits on its own in-progress result. Pages deployment status is separate from these code-validation checks.

## Integration validation before activation

Use injected transport and GitHub GET fakes; no real owner token is needed for this preparation.

- Disabled host: zero Edge calls and zero GitHub calls.
- Wrong task/repository/inputs/permissions: no provider invocation; claimed scope failures are fenced and blocked.
- Allowed task: one claim, files and CI tied to one SHA, each AgentRunner state transition saved with current revision/generation, completion clears the lease.
- Same SHA with stale successful CI, pending/failing latest attempt, incomplete pagination, main movement or malformed file response: no successful verification.
- Expired lease, stale revision, activity failure and response lost after committed save: stop; do not reissue an ambiguous POST or run a second task automatically.
- Provider failures and redirects: no credential appears in returned error, task state, activity, repr or ordinary traceback.
- Permissions: only `contents:read` and `actions:read`; no new secret, grant, dispatch or scheduled execution.

After these tests pass, review `HOSTED_READONLY_ACTIVATION.md`. Live hosted execution still requires separate user authorization and an available owner session. A passing fake integration test is not a successful live Edge-to-worker validation.

## Next implementation slice

Prepare the SHA-pinned GitHub observation/verification behavior and its regression tests first. Then add the closed-by-default composition factory and trusted-task policy with an injected end-to-end test. Keep these changes separate from live host/session provisioning.

Long-lived authentication, always-on scheduling, general generation providers, sales ingestion and 21:00 report delivery remain later work. Unknown sales are never zero-filled.

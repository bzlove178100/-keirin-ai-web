# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless the user explicitly authorizes a new, specific boundary:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**.

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. Exact-task lease acquisition is deployed. No always-on worker is active.

Latest direct read-only staging verification: 2026-09-26, refresh-provider work (no live run started):

- single-active trusted-run guard: **present**;
- fresh trusted tasks currently `queued` / `running`: **0**;
- `race_predictions`: **0 rows**.

## Keirin prospective evaluation

- Owner-only dry-run remains the validation path.
- Unknown odds are not invented.
- Probabilities remain uncalibrated for monetary EV / production promotion.
- First eligible new prospective history: 2026-09-24 Ito Onsen 1R, 7 riders, all 210 model probabilities, 72 confirmed pre-race trifecta odds, valid chronology and supervised-training eligibility.
- Real prospective collection remains 1 distinct eligible prediction time. Four more distinct times are required to reach the evaluator's five-time technical minimum; boundary purging can require more. Five is not evidence of accuracy or profitability.

## Shared autonomous-agent milestones

Key merged milestones:

- PR #32–#37: broad goal, `TaskSpec`, durable state, activity ledger, permission model, reconciliation, runtime bridge, provider-neutral read-only adapters and report contracts.
- PR #40: verified GitHub read-only provider path.
- PR #45–#47: queue planning, interruption safety, locking and immutable TaskSpec fingerprint binding.
- PR #52 / #54: owner-only hosted checkpoint persistence and strict `HostedCheckpointClient`.
- PR #56: owner-only append/read activity persistence and strict `HostedActivityClient`.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict queue client and explicit expired-lease reconciliation.
- PR #58–#60: fail-closed worker coordination, explicit execution gate and credential-isolated Supabase Edge transport.
- PR #62–#64: SHA-pinned GitHub observation/CI verification, durable provider evidence, recovery inspection and hard run deadline.
- PR #65 (`826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`): proposal-only recovery decisions and committed closed single-run activation manifest.
- PR #66: first bounded read-only integration-trial record plus fail-closed standalone one-shot host entrypoint.
- PR #67–#70: strict trusted run-instance identity, exact-task claim client, exact worker binding and instance-bound CLI/recovery.
- PR #71: separate owner-only exact-claim Edge path and credential-isolated routing.
- PR #72: idempotent trusted run-instance enqueue preparation; consumed instances fail closed and enqueue never claims or executes.
- PR #73: recorded the prepared enqueue boundary and then-current staging safety state.
- PR #74: recorded the newly authorized bounded read-only validation evidence then available.
- PR #75 (`8b17f67c8858fedf5494c738217169e33f1336fe`): added a database-level partial unique guard allowing at most one fresh `keirin-readonly-status-check.*` task in `queued` or `running` per owner; also made enqueue fail closed when another distinct trusted run owns the active slot. All required PR workflows passed before merge. The guard migration was then applied to staging.
- PR #76 (`2eda84c768edb53e9e9429b7f18761a37bac7ffa`): bound manual one-shot authorization to one exact instance token through `KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN`, made the standalone host self-enqueue/verify the same pristine TaskSpec before worker construction, and retained exact-task claim plus same-instance recovery. All four PR workflows passed before merge.
- PR #77 (`ead3368968deb2f4c889f3061f07371a0610977f`): added a **manual `workflow_dispatch`-only** GitHub Actions one-shot host with `contents:read` / `actions:read`, fixed concurrency, 5-minute timeout, exact token confirmation and static safety regression. It has **not been dispatched** in this work. No schedule or recurrence was added.

- PR #78 (`5ddae8161abba6d8d4ffee725c16db6b9b5d45f8`): synchronized this work-status record before authentication-boundary work.
- PR #79 (`4ad117907e4416d8ebeba9d14209884cf1f0c5ed`): added redacted local credential preflight, HTTPS-origin/exact-instance validation and known-expiry TTL rejection before the manual one-shot worker. Unknown expiry remains explicit; `AUTH_SESSION_LIFECYCLE.md` defines the refresh-provider boundary. All four PR workflows passed.
- PR #80 (`d85e6c008fc725accf5fd63a19a6c945457c37d4`): completed `CredentialProvider`, redacted `CredentialSnapshot`, static in-memory access provider, typed errors, package exports and regression integration. Added 19 tests, including fail-closed scopes/lifetimes, revocation and rotation without immutable TaskSpec changes or completed-task replay. Rejected malformed/non-finite TTL and timestamp inputs; removed untrusted lookup/scope values from errors. All 36 Python regression commands passed locally and all four required PR workflows passed before merge. The four main push workflows and Pages deployment also passed at this merge SHA.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves, explicit expired-lease reconcile-to-blocked and the single-active trusted-run guard.

Deployed functions relevant to the agent:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**, service `v1-owner-trusted-run-exact-claim`. It accepts only `queue_claim_task` for fresh trusted run-instance IDs and reports task execution, production prediction, prediction DB writes, external race-data fetch, provider generation and report delivery all disabled.

Verified database controls include:

- exact-task claim RPC available to authenticated owner path and not anonymous callers;
- owner-scoped queue/checkpoint/activity state;
- one active fresh trusted status-run per owner enforced by a partial unique index;
- `race_predictions` remains `0`.

## Bounded live read-only validation history

### Original bounded trial

The first explicit authorization was consumed by the original template-task trial. It demonstrated real GitHub read-only provider access plus staging queue/checkpoint/activity persistence while leaving `race_predictions=0`. It did not prove an always-on host or scheduler.

### Later bounded authorization and concurrency finding

The user later explicitly authorized one additional bounded read-only validation. That authorization is **consumed** and is not permission for another live run.

The initially documented exact run instance was:

- `keirin-readonly-status-check.aebc2bc4a1703796`;
- final status `completed`;
- revision `3`;
- attempt count `1 / 1`;
- lease generation `1`;
- lease cleared after completion.

A post-run database audit then found that a second distinct fresh trusted run had also been activated during the same authorization window:

- `keirin-readonly-status-check.8f6130bb98a7a8ae`;
- final status `completed`;
- revision `6`;
- attempt count `1 / 1`;
- lease generation `1`.

Both rows are now terminal, and the latest staging query shows **0 active trusted runs**. This concurrency was treated as a defect because the human authorization was for one run, even though the recorded tasks stayed within the read-only status-run family. No further live run was started to test the fix.

PR #75 added the database-level single-active guard. PR #76 additionally bound host authorization to one exact runtime instance token and made enqueue part of the same standalone one-shot path. PR #77 prepared a serialized manual GitHub Actions host on top of those controls.

## Manual independent one-shot host: prepared, not activated

The independently hosted manual path is now prepared in code:

1. a human manually dispatches `.github/workflows/agent-manual-one-shot.yml`;
2. dispatch requires a fresh 16-character lowercase hex instance token and literal `RUN_EXACTLY_ONCE` confirmation;
3. workflow permissions are read-only (`contents:read`, `actions:read`);
4. fixed Actions concurrency permits only one manual one-shot job at a time;
5. the host requires `KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN` to equal the exact CLI token;
6. the host creates/verifies exactly that pristine queued TaskSpec;
7. staging rejects a second distinct active trusted run for the same owner;
8. the worker exact-claims only that TaskSpec through `agent-exact-claim-dev`;
9. AgentRunner state changes are fenced/CAS-persisted and recovery stays on the same identity;
10. the workflow stops after one job and has no cron/schedule/recurrence trigger.

`tools/inspect_manual_host_config.py` now checks runtime configuration locally before the worker call. Known-expired/short bearer TTL and instance/origin mismatches fail closed. Opaque expiry may support the bounded manual path but is not long-lived readiness.

The workflow references runtime configuration through GitHub Actions variables/secrets:

- `SUPABASE_PROJECT_URL`;
- `SUPABASE_PUBLISHABLE_KEY`;
- `SUPABASE_OWNER_BEARER_TOKEN`;
- ephemeral `${{ github.token }}` for GitHub reads.

**The presence or freshness of the three Supabase Actions values has not been verified or configured in this chat.** No credential value is committed to the repository.

The workflow has **not been dispatched**. A future dispatch is a new live-execution boundary and requires explicit authorization for that fresh instance.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, single-active-run protection, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, durable provider evidence, recovery inspection/proposals, hard deadline enforcement, an exact-token-bound standalone one-shot host, a manual GitHub Actions host, redacted credential preflight and tested static credentials and an access-only refresh-provider boundary with terminal authentication failure states.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, report delivery is not configured, and deployed runtime task execution remains OFF.

## Next work / next boundary

Code-only work may continue without another live-run authorization. Static credentials and the generic refresh-capable provider are implemented and regression-covered, but neither provider is wired into the host. The refresh provider uses an injected `HostCredentialSource` that returns access-only grants. No concrete source, durable secret store or actual token refresh has been configured or run.

Current refresh behavior: exact provider/account/capability matching, known-expiry TTL enforcement, monotonic elapsed-time checks, one in-flight refresh per object, source/local revocation, and terminal `blocked_auth` without fallback or automatic retry. Runners/adapters receive no refresh-secret handle. Credential rotation tests preserve TaskSpec identity and do not replay completed work.

The source/secret-store design in `AUTH_SESSION_LIFECYCLE.md` explicitly leaves remote identity verification, distributed refresh fencing, durable refresh-token rotation and ambiguous-outcome recovery to a concrete host source. Current tests use only a fake source. The 26 refresh-provider tests and all 37 Python regression commands passed locally. A `ready` report or `refresh_capable=True` is not execution authorization.

Next: implement and fault-test the versioned host secret-store/exchange boundary, then design a runner/adapter binding that blocks work on authentication failure before provider actions. Keep the existing manual preflight unchanged and all long-lived host, scheduler and recurrence gates OFF.

A future manual workflow dispatch or any other new hosted execution requires a new explicit live-run authorization. Do not infer such authorization from code merge, workflow presence, or prior one-run approvals.

Generation providers, recurring scheduler, prediction writes, race-data auto-fetch and report delivery remain separate later boundaries.

No race screenshots or owner credential resend is needed for current code-only preparation.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

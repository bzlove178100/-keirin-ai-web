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

Latest direct read-only staging verification during credential-boundary work; no live run was started:

- single-active trusted-run guard: **present**;
- fresh trusted tasks currently `queued` / `running`: **0**;
- `race_predictions`: **0 rows**;
- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**;
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**.

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
- PR #66–#72: bounded integration evidence, trusted run-instance identity, exact-task claim, exact worker binding, exact-claim Edge path and idempotent enqueue preparation.
- PR #75 (`8b17f67c8858fedf5494c738217169e33f1336fe`): one-active-fresh-trusted-run-per-owner database guard after the two-run concurrency defect was found.
- PR #76 (`2eda84c768edb53e9e9429b7f18761a37bac7ffa`): exact runtime instance-token binding and self-enqueue/verify before worker construction.
- PR #77 (`ead3368968deb53e9e9429b7f18761a37bac7ffa`): manual `workflow_dispatch`-only one-shot host with read-only GitHub permissions, fixed concurrency and timeout; it has not been dispatched by current code-only work.
- PR #79 (`4ad117907e4416d8ebeba9d14209884cf1f0c5ed`): redacted runtime credential preflight and authentication/session lifecycle boundary.
- PR #80 (`d85e6c008fc725accf5fd63a19a6c945457c37d4`): static `CredentialProvider`, redacted `CredentialSnapshot`, typed lifetime/scope/revocation failures and CI coverage.
- PR #82 (`f684bfc3e8409558d508ad521113caaf88420253`): access-only `RefreshingCredentialProvider` / `HostCredentialSource`, exact provider/account/capability validation, TTL/clock-rollback protection, single-object refresh exclusion, terminal auth failure and rotation without TaskSpec identity changes.
- PR #83 (`30920f298c3ac8083ca764935369edc7e28b5237`): offline/reference versioned refresh-secret store/exchange boundary with strict CAS/fencing, durable `refreshing` ownership, rotation generation, ambiguous-outcome blocking, operator recovery and fault injection.
- PR #84 (`02e71c2a587cf3f55ee5b6d1671c5b5a9489fbea`): synchronized this status after the versioned refresh-secret boundary.
- PR #85 (`df6100cd6ba4bfea834659417ef482ad78922456`): hardened attempt IDs and failure metadata, mapped secret-store errors to fixed redacted outward failures, and added hostile-error regression coverage. All four required PR workflows passed before merge.
- PR #86 (`f0594f6376f82805d311d9bd9a0ab4b0bc1aba6c`): added `DurableVersionedSecretStore` and `DurableSecretBackend` contract with opaque binding keys, strict schema/binding validation, atomic CAS outcome classes, exact read-back verification and fake-backend fault injection. No real durable secret backend was configured. All four required PR workflows passed before merge.
- PR #87 (`6031eac456cfeb834e9fcb31a20da7b671099e99`): added `CredentialBoundToolAdapter` / `CredentialRequirement` so access-only credential acquisition occurs before an underlying provider action. Credential failures become fixed terminal `BlockedAction` states before provider invocation; snapshots exist only in local action context, requirements cover every action/verifier and tests verify persisted state/activity do not contain the credential secret. All four required PR workflows passed before merge.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves, explicit expired-lease reconcile-to-blocked and the single-active trusted-run guard.

Deployed agent functions:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**. It accepts only exact fresh trusted status-run claim operations and does not enable task/provider execution.

PR #82–#87 did not perform a migration, Edge deployment, provider refresh, secret-store integration or live task execution.

## Bounded live read-only validation history

The previous one-run authorization is consumed and is not permission for another live run. During that authorization window two distinct fresh trusted read-only run instances completed; this was treated as a defect even though they remained in the read-only status-task family. Both rows are terminal. PR #75 added the database-level single-active guard; PR #76 added exact instance authorization; PR #77 prepared a serialized manual one-shot host. No further live run has been used to test those later controls.

A future workflow dispatch or any new hosted execution requires a new explicit live-run authorization. Code merge, workflow presence, persistence authorization or earlier one-run approvals are not execution authorization.

## Credential / authentication boundary

Current implemented layers:

1. **Static access provider** — in-memory bounded/manual-host access snapshot, no refresh.
2. **Generic refresh provider** — access-only grants from an injected `HostCredentialSource`, exact binding/TTL checks and terminal fail-closed auth state.
3. **Versioned refresh source/store** — CAS refresh ownership, attempt fencing, rotated-secret persistence before access return, durable ambiguous blocking and evidence-based operator recovery.
4. **Durable backend adapter contract** — opaque binding key, schema/binding validation, explicit conflict/ambiguous/unavailable backend outcomes and exact CAS read-back. Only a fake backend is tested; no real durable secret store is connected.
5. **Credential-gated tool adapter** — acquires an access-only snapshot before each underlying provider action/verifier and blocks before provider invocation when authentication is unavailable. The snapshot is local action context only and is not task/checkpoint/activity state.

`InMemoryVersionedSecretStore` and fake durable backends are reference/fault-test implementations only. No real OAuth/token refresh is configured or called. `DURABLE_SECRET_STORE_ADAPTER.md`, `SECRET_STORE_RECOVERY.md`, `CREDENTIAL_GATED_ADAPTER.md` and `AUTH_SESSION_LIFECYCLE.md` describe the boundaries.

A blocked credential-gated task is not silently retried after authentication repair. Since `AgentRunner` records the step attempt before action invocation, a later retry requires explicit reconciliation proving that no underlying provider action ran.

The generic wrapper prevents a `CredentialSnapshot` object from being returned as action data, but cannot infer whether an arbitrary string is a token. Concrete provider adapters remain responsible for never returning/logging credential strings and for using only the injected snapshot in provider authentication headers/transport state.

## Current agent state

The project has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, single-active-run protection, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, recovery inspection/proposals, hard deadline enforcement, one-shot host preparation, tested static/refresh access providers, versioned refresh-secret CAS/recovery, a durable-store adapter contract and a pre-provider credential gate.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, report delivery is not configured, deployed runtime task execution remains OFF, and no real durable secret store/auth refresh integration is configured.

## Next work / next boundary

Code-only work may continue without another live-run authorization.

Next safe slice:

1. add a host credential-binding registry that pins action -> provider/account/capability requirements independently of TaskSpec input;
2. reject adapter/task attempts to select or override credential provider/account from untrusted task args;
3. add recovery evidence distinguishing `credential_unavailable_before_provider` from ambiguous provider-side effects so reconciliation can prove a safe retry path;
4. keep real secret-store/provider integration, live hosted task execution, scheduler/recurrence and new provider permissions as separate later boundaries.

Generation providers, prediction writes, race-data auto-fetch and report delivery remain separately disabled.

No race screenshots or owner credential resend is needed for current code-only preparation.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

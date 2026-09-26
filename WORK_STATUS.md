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

Latest direct read-only staging verification: 2026-09-26 during versioned-secret-store work; no live run was started:

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
- PR #77 (`ead3368968deb2f4c889f3061f07371a0610977f`): manual `workflow_dispatch`-only one-shot host with read-only GitHub permissions, fixed concurrency and timeout; it has not been dispatched by current code-only work.
- PR #79 (`4ad117907e4416d8ebeba9d14209884cf1f0c5ed`): redacted runtime credential preflight and authentication/session lifecycle boundary.
- PR #80 (`d85e6c008fc725accf5fd63a19a6c945457c37d4`): static `CredentialProvider`, redacted `CredentialSnapshot`, typed lifetime/scope/revocation failures, 19 tests and CI integration.
- PR #81: synchronized this status before refresh-provider implementation.
- PR #82 (`f684bfc3e8409558d508ad521113caaf88420253`): `RefreshingCredentialProvider` and `HostCredentialSource` boundary. It exposes access-only credential snapshots, pins provider/account/capabilities, validates TTL, prevents simultaneous refresh in one provider object, makes refresh failure terminal `blocked_auth`, prioritizes revoke, prevents clock rollback from extending TTL and preserves immutable TaskSpec identity across credential rotation. Its 26 dedicated tests and all required PR/main workflows passed; Pages also passed.
- PR #83 (`30920f298c3ac8083ca764935369edc7e28b5237`): added the offline/reference versioned refresh-secret store and exchange boundary with strict version CAS/fencing, fixed refresh attempt IDs, durable `refreshing` ownership before provider contact, rotated-secret persistence before access return, explicit `blocked_auth` / `blocked_ambiguous`, read-back handling for ambiguous store writes, operator-only recovery, revocation and fault-injection/concurrency tests. The first PR run found that provider exceptions remained in Python exception context; the implementation was changed so outward fixed errors are raised after leaving the provider exception handler. All four required PR workflows then passed. After merge, the four main push workflows and Pages deployment also passed.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves, explicit expired-lease reconcile-to-blocked and the single-active trusted-run guard.

Deployed agent functions:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**. It accepts only exact fresh trusted status-run claim operations and does not enable task/provider execution.

No migration, Edge deployment or live task execution was performed by PR #82 or PR #83.

## Bounded live read-only validation history

The previous one-run authorization is consumed and is not permission for another live run. During that authorization window two distinct fresh trusted read-only run instances completed; this was treated as a defect even though they remained in the read-only status-task family. Both rows are terminal. PR #75 added the database-level single-active guard; PR #76 added exact instance authorization; PR #77 prepared a serialized manual one-shot host. No further live run has been used to test those later controls.

A future workflow dispatch or any new hosted execution requires a new explicit live-run authorization. Code merge, workflow presence, persistence authorization or earlier one-run approvals are not execution authorization.

## Credential / authentication boundary

Current implemented layers:

1. **Static access provider** — in-memory, bounded/manual-host credential snapshot, no refresh.
2. **Generic refresh provider** — access-only grants from an injected `HostCredentialSource`; exact provider/account/capability match, TTL enforcement, monotonic elapsed time, local single-flight refresh, terminal auth failure and revoke semantics.
3. **Versioned source/store reference contract** — version-CAS refresh ownership, fixed attempts, rotation generation, durable block on ambiguous provider/store outcomes and explicit evidence-based recovery.

`InMemoryVersionedSecretStore` is a reference/fault-test implementation only. It is **not** a production secret store. `RefreshExchange` is an interface only; no real OAuth/authentication refresh is configured or called.

`SECRET_STORE_RECOVERY.md` records the contract: a real store must provide cross-process atomic CAS/fencing and host-only secret protection; a real exchange must validate provider identity/scopes, bound timeouts and return rotated material through the host-only boundary. Ambiguous outcomes are never automatically retried.

Runners/adapters still have no refresh-secret handle. Access snapshots remain the only intended provider-facing credential view.

## Current agent state

The project has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, single-active-run protection, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, recovery inspection/proposals, hard deadline enforcement, an exact-token-bound standalone one-shot host, a manual GitHub Actions host, redacted credential preflight, tested static/refresh access credential providers, and an offline versioned refresh-secret CAS/recovery contract.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, report delivery is not configured, deployed runtime task execution remains OFF, and a real durable secret store/auth refresh integration is not configured.

## Next work / next boundary

Code-only work may continue without another live-run authorization.

Next safe slice:

1. harden the versioned-store safe metadata contract: fixed failure classifications and safe attempt-ID format;
2. ensure secret-store adapter failures cannot leak provider/store exception payloads through outward exception context/logging;
3. define a concrete durable-store adapter contract and fault-test it without deploying new secret storage;
4. design the runner/adapter credential binding so authentication failure blocks the task before any provider action;
5. keep refresh-provider integration, live secret storage, scheduler/recurrence and new hosted execution as separate later boundaries.

Generation providers, prediction writes, race-data auto-fetch and report delivery remain separately disabled.

No race screenshots or owner credential resend is needed for the current code-only work.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

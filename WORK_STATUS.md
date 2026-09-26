# Work status

Updated: 2026-09-27 (Asia/Tokyo).

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

Latest direct read-only staging verification: 2026-09-26 during authentication-boundary work; no live run was started:

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
- PR #83 (`30920f298c3ac8083ca764935369edc7e28b5237`): offline/reference versioned refresh-secret store and exchange boundary with strict version CAS/fencing, durable `refreshing` ownership before provider contact, rotated-secret persistence before access return, explicit `blocked_auth` / `blocked_ambiguous`, read-back handling for ambiguous store writes, operator-only recovery, revocation and concurrency/fault-injection tests. Provider exceptions are converted to fixed outward errors after leaving exception handlers. All required PR/main workflows and Pages passed.
- PR #84 (`02e71c2a587cf3f55ee5b6d1671c5b5a9489fbea`): synchronized the verified PR #83 boundary and staging safety state.
- PR #85 (`df6100cd6ba4bfea834659417ef482ad78922456`): hardened secret-store safe metadata and error redaction. Persisted failure values are fixed classifications, refresh attempt IDs use a log-safe format, store/recovery failures are mapped to fixed outward errors and malicious error-payload tests were added. Required PR workflows passed before merge.
- PR #86 (`f0594f6376f82805d311d9bd9a0ab4b0bc1aba6c`): added `DurableVersionedSecretStore` and a provider-neutral durable-backend contract. Binding keys are opaque SHA-256 identifiers, stored records/CAS read-back are validated, backend conflict/ambiguous/unavailable conditions are mapped to fixed errors, and fake-backend fault injection verifies composition with `VersionedHostCredentialSource`. No real backend was connected.
- PR #87 (`6031eac456cfeb834e9fcb31a20da7b671099e99`): added `CredentialBoundToolAdapter` and per-action `CredentialRequirement`. Credentials are acquired before provider actions/verifiers, access-only snapshots are injected only into local in-memory action context, auth failures block before provider invocation and terminal blocked tasks do not silently retry. No real provider was connected.
- PR #88 (`719245a36c56d0c431ef2cd65cb1befdb5122eb6`): hardened the credential-gated provider boundary so credential-source/provider-action exception payloads are not persisted, provider `BlockedAction` reasons are replaced with fixed classifications, and action results containing a credential snapshot or any access-secret value are rejected. Dedicated leak/regression tests passed. All four PR workflows passed before merge; all four main push workflows and Pages deployment passed after merge.
- PR #89 (`b9f4abdbd9bcd29239af08df151345bec24ea910e`): synchronized this status through the durable authentication and credential-gating work.
- PR #90 (`0c7021371d0829766454ef847a93903e747139e4`): added the offline composition contract `DurableSecretBackend -> DurableVersionedSecretStore -> VersionedHostCredentialSource -> RefreshingCredentialProvider -> CredentialBoundToolAdapter`. The factory accepts no raw refresh secret and performs no network I/O, seeding, migration, dispatch or background work. End-to-end fake-backend/exchange tests cover successful rotation, ambiguous exchange, ambiguous durable commit read-back, CAS claim conflict, revocation, completed-task no-replay and absence of access/refresh credential material from `FileStateStore` task/activity persistence. All four required PR workflows passed before merge.
- PR #91 (`315c9e87cc607f0669cef2f5752dd27ec1e55ce2`): introduced `SafeActionError` and changed `AgentRunner` so arbitrary untyped action/verifier exception text is never written to durable task/activity state by default. Credential-gated action failures use fixed safe codes, runtime-bridge `blocked_reason` values are treated as untrusted, and read-only worker invariant failures use explicit safe classifications. The first PR CI run exposed one expected invariant-code mismatch; it was fixed by classifying that known internal read-only violation with `SafeActionError`, after which all four PR workflows passed. After merge, all four main push workflows and Pages deployment also passed.
- PR #92 (`e13a6a9e9507e9545b332a81c08620b65a673f74`): synchronized this status through the safe action-error milestone.
- PR #93 (`8b777c439b1571c8b17f25f1dae4edbb2ab7931a`): added an explicitly injected host-only ephemeral diagnostic sink. It receives only constrained metadata (task/step/action, phase, attempt, retry flag, fixed classification and sanitized exception class name), never exception text/repr, task inputs, args, results, credential snapshots or provider responses. Sink failure is best-effort and cannot change retry/task semantics. Dedicated tests and all four PR workflows passed before merge; the queried main workflow set completed with no failures observed.
- PR #94 (`b39ee38c4b6bd791e60d204c17e28b6cf509349c`): added an AST-based persistence-redaction guard so future caught exception objects cannot flow directly into `last_error`, `blocked_reason`, durable events or `BlockedAction`, and pinned runtime-bridge blocked handling to `runtime_bridge_blocked`. PR regression, collection-progress and PostgreSQL-contract workflows passed before merge; post-merge main workflows were checked separately.
- PR #95: added `REAL_AUTH_INTEGRATION_REQUIREMENTS.md` as the pre-activation security and operational gate for any concrete backend or provider refresh exchange.
- PR #96 (`a6ec19dd709cce78c870afa30d882977ea72adbf`): added the reusable synthetic-only durable-backend conformance harness, covering CAS/conflict, read-back, new-client persistence and injected ambiguous outcomes. It does not establish multi-process or real backend safety.
- PR #97 (`ba982f9da0d0c237dd6de39f5e98865d90431d15`): added a synthetic-only SQLite backend under `tests/support`, ran the reusable harness against it, and verified a two-process CAS race with one winner and one conflict. The 2 dedicated tests, 2 harness tests and 11 durable-store tests passed locally; all four PR workflows passed before merge. No encryption or production backend readiness is implied.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves, explicit expired-lease reconcile-to-blocked and the single-active trusted-run guard.

Deployed agent functions:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**. It accepts only exact fresh trusted status-run claim operations and does not enable task/provider execution.

PR #82–#97 did not deploy a new Edge Function, apply a secret-store migration, perform a real authentication refresh or start a live hosted run.

Read-only secret-backend catalog review on 2026-09-27 confirmed PostgreSQL `17.6`,
`supabase_vault` `0.3.1`, and effective schema/object access for `service_role` to the
Vault secret/decrypted views and create/update functions. `anon`, `authenticated` and
`authenticator` lack the inspected schema/read/execute privileges. No secret rows or
keys were read. Existing role grants were not changed. This review did not recheck the
earlier task counts or deployed function versions above.

## Bounded live read-only validation history

The previous one-run authorization is consumed and is not permission for another live run. During that authorization window two distinct fresh trusted read-only run instances completed; this was treated as a defect even though they remained in the read-only status-task family. Both rows are terminal. PR #75 added the database-level single-active guard; PR #76 added exact instance authorization; PR #77 prepared a serialized manual one-shot host. No further live run has been used to test those later controls.

A future workflow dispatch or any new hosted execution requires a new explicit live-run authorization. Code merge, workflow presence, persistence authorization or earlier one-run approvals are not execution authorization.

## Credential / authentication boundary

Current implemented layers:

1. **Static access provider** — in-memory bounded/manual-host credential snapshots, no refresh.
2. **Generic refresh provider** — access-only grants from an injected `HostCredentialSource`; exact provider/account/capability match, TTL enforcement, monotonic elapsed time, local single-flight refresh, terminal auth failure and revoke semantics.
3. **Versioned refresh source/store contract** — version-CAS refresh ownership, attempt fencing, rotation generation, durable blocking on ambiguous provider/store outcomes and explicit evidence-based recovery.
4. **Durable backend adapter contract** — backend-neutral CAS/read/write adapter with opaque binding keys, strict schema/integrity checks and fixed failure mapping. The implementation is tested against synthetic fixtures only; no real secret backend is connected.
5. **Credential-gated provider adapter** — per-action capability/TTL policy, pre-action credential acquisition, local access-only snapshot injection, fixed auth/provider failure classifications and result leak detection.
6. **Offline full-stack composition** — a dependency-injection factory composes the durable backend/store/source/provider/gated-adapter chain without accepting raw refresh material or activating a service.
7. **Persistence-safe action errors** — `AgentRunner` persists only validated `SafeActionError` codes or fixed redacted classifications for untyped action/verifier exceptions; runtime bridge blocked payloads are not copied into persistent state.
8. **Ephemeral diagnostics** — optional host-injected failure metadata sink, explicitly non-durable and payload-free; it cannot weaken the persistent redaction contract.
9. **Static redaction audit** — CI scans the core for direct caught-exception flows into persistent error fields/events and verifies fixed runtime-bridge block classification.

`InMemoryVersionedSecretStore` is reference/fault-test only. `DurableVersionedSecretStore` defines the contract around a future host-only durable backend but is not itself a configured production backend. `RefreshExchange` remains an interface only; no real OAuth/authentication refresh is configured or called.

Runners/adapters receive no refresh-secret handle. Provider actions receive only an access snapshot through the credential-gated local context. The wrapper rejects action results that contain the snapshot or access secret and replaces provider exception text with fixed classifications before `AgentRunner` persistence.

`REAL_AUTH_INTEGRATION_REQUIREMENTS.md` is the current pre-activation review contract for any future real backend/exchange. It requires encrypted host-only secret ownership, distributed atomic CAS, bounded/no-blind-retry refresh I/O, durable rotated-secret persistence before access return, explicit `blocked_ambiguous` recovery, revocation precedence, fixed audit metadata, crash/restart testing and a staged activation sequence that does not bind live task execution in the same change.

`STAGING_SECRET_BACKEND_DESIGN.md` selects Vault plus private PostgreSQL metadata for an
offline prototype. It specifies a dedicated database identity, narrow private functions,
atomic secret/metadata CAS, primary read-back and fixed failure classification. Activation
is blocked pending effective isolation (including current service-role Vault access), key
lifecycle, bootstrap credential, logging/restore and real-backend fault-test evidence.
`ops/credential_vault_inventory.sql` was executed successfully as a catalog-only query;
it is an inventory, not a readiness check.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, single-active-run protection, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, recovery inspection/proposals, hard deadline enforcement, an exact-token-bound standalone one-shot host, a manual GitHub Actions host, redacted credential preflight, static and refresh-capable credential providers, version/CAS refresh-secret recovery semantics, a durable secret-backend adapter contract, an offline full credential-stack composition path, a credential-gated provider-action boundary, persistence-safe action/verifier error handling, ephemeral diagnostic metadata and a static persistence-redaction audit.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, report delivery is not configured, deployed runtime task execution remains OFF, and no real durable secret backend or real provider refresh exchange is connected.

## Next work / next boundary

Code-only work may continue without another live-run authorization.

Next safe slice:

1. implement the private SQL read/CAS and ACL contract in an isolated local PostgreSQL fixture using synthetic Vault functions, including rollback and cross-binding denial tests, following `STAGING_SECRET_BACKEND_DESIGN.md`;
2. implement the host adapter with bounded injected connection handling and fixed errors; keep all credentials synthetic during code/CI verification;
3. close the documented operational gates and review a separate staging migration before real-backend conformance or provider refresh integration;
4. keep live hosted execution, long-lived host, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery disabled until separately authorized.

No race screenshots or owner credential resend is needed for the current code-only work.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

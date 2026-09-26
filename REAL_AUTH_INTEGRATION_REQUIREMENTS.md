# Real authentication integration requirements

This document defines the security and operational gate for connecting a **real durable
refresh-secret backend** and a **real provider refresh exchange** to the autonomous-agent
credential stack.

It is a design/review contract only. It does **not** configure a secret manager, OAuth
client, external provider, hosted worker, scheduler, production prediction path or report
delivery.

The already implemented offline chain is:

`DurableSecretBackend -> DurableVersionedSecretStore -> VersionedHostCredentialSource -> RefreshingCredentialProvider -> CredentialBoundToolAdapter -> AgentRunner`

A real integration must preserve every fail-closed property already tested by that chain.

## 1. Separation of responsibilities

A production implementation must keep these roles separate:

- **Secret backend**: stores host-only refresh material and version/fencing metadata.
- **Refresh exchange**: performs exactly one provider refresh request for one claimed attempt.
- **Credential source**: coordinates claim, provider exchange, rotated-secret persistence,
  ambiguous-outcome blocking and explicit recovery.
- **Credential provider**: exposes access-only snapshots with provider/account/capability and
  TTL validation.
- **Tool adapter**: receives only access material required by that action.
- **Runner / task state / activity ledger**: never receives or persists refresh material.

No task input, TaskSpec field, checkpoint, activity event, report, public Web response or
GitHub artifact may contain a refresh token or equivalent long-lived credential.

## 2. Durable secret ownership and encryption

A concrete backend must prove all of the following before activation:

1. Refresh secrets are encrypted at rest with a managed key or equivalent host-controlled
   encryption boundary.
2. Decryption capability is available only to the minimal host identity that performs the
   refresh operation.
3. Application/browser/client-side identities cannot read refresh material.
4. Secrets are not copied into environment dumps, debug bundles, CI artifacts, logs,
   analytics, traces, exception payloads or support exports.
5. Backups, replicas and point-in-time recovery are covered by the same confidentiality
   policy.
6. Key rotation has an explicit procedure that does not require exposing plaintext values.
7. Decommission/revocation includes deletion or cryptographic invalidation of obsolete
   secret material where supported.

## 3. Atomic CAS and distributed refresh fencing

`compare_and_swap(binding_key, expected_version, replacement)` must be atomic across all
processes, regions and workers that may refresh the same binding.

Required semantics:

- one version transition wins;
- a stale writer receives a definite conflict classification;
- conflict means the submitted replacement definitely did not become current;
- a timeout/network loss that cannot prove commit or non-commit is **ambiguous**, not a
  retryable conflict;
- reads after a claimed refresh must observe a single authoritative version order;
- storage replication lag must not allow two refresh owners to both proceed;
- refresh ownership is recorded before contacting the provider;
- attempt IDs remain bounded, opaque/log-safe identifiers and are not secrets.

A multi-process concurrency test must be run against the real backend before any live
provider refresh is enabled.

## 4. Provider refresh request contract

A real `RefreshExchange` implementation must:

- pin one provider endpoint/origin and expected protocol;
- use bounded connect/read/total timeouts;
- perform no hidden automatic retry by the HTTP/OAuth client;
- send only the refresh material and fields required by the provider contract;
- validate TLS normally and never disable certificate verification;
- validate provider/account identity where the provider exposes it;
- validate granted scopes/capabilities against the pinned binding;
- validate access-token issue/expiry times and minimum usable TTL;
- require a non-empty rotated refresh secret when the provider rotates refresh tokens;
- classify a provider rejection as definite only when the provider response proves the
  refresh request did not yield a usable rotated credential;
- classify timeout, connection loss, malformed/incomplete response, uncertain provider
  state and unexpected transport/library failure as **ambiguous** unless the provider's
  documented semantics prove non-application.

The refresh exchange must never return refresh material to the runner or tool adapter.

## 5. No blind retry after ambiguous outcome

This is a hard requirement.

When it is unknown whether the provider consumed/rotated the refresh token, the system
must enter `blocked_ambiguous` and stop issuing provider work for that binding.

It must **not**:

- retry the old refresh token automatically;
- fall back to a previous stored refresh token;
- race another host/process to refresh;
- mark the attempt successful because an access call later happens to work;
- clear the block because a process restarted.

Recovery requires external evidence and an explicit operator path.

## 6. Rotated-secret persistence ordering

A new access grant may be released to `RefreshingCredentialProvider` only after the
rotated refresh secret and its generation/version metadata are durably committed.

Required order:

1. CAS claim `ready -> refreshing`.
2. Provider refresh request exactly once for that claim.
3. Validate the complete provider response.
4. Persist rotated refresh secret with CAS.
5. Read back/confirm the committed version when the backend write outcome is uncertain.
6. Only then return the access-only grant.

If step 4/5 is ambiguous, block authentication. Do not use the access token while losing
track of the refresh chain.

## 7. Crash and restart behavior

A process may stop at any instruction boundary. Recovery must be safe for these cases:

- crash before claim commit;
- crash after claim commit but before provider request;
- crash during provider request;
- crash after provider success but before secret-store commit;
- crash during/after ambiguous secret-store commit;
- crash after secret-store commit but before access grant is returned.

A persisted `refreshing` or `blocked_ambiguous` state must not be auto-cleared merely by
host restart or lease expiry. The system must distinguish task leases from credential
refresh ownership.

## 8. Revocation

Revocation must dominate concurrent issuance/refresh.

Requirements:

- once revocation is durably observed, no new access snapshot may be issued;
- refresh-secret material should be cleared/invalidated where the backend permits;
- a refresh completing concurrently with revocation must not resurrect the binding;
- provider-side revocation/disconnect should be available as a separate operator action
  where supported;
- local revocation and provider revocation outcomes must be auditable without storing
  credential values.

## 9. Logging, diagnostics and audit metadata

Durable logs may contain fixed classifications and non-secret metadata only.

Allowed examples:

- provider identifier from trusted host configuration;
- opaque binding key;
- version / refresh generation;
- log-safe attempt ID;
- fixed state (`ready`, `refreshing`, `blocked_auth`, `blocked_ambiguous`, `revoked`);
- fixed failure classification;
- timestamps and operation duration;
- operator/recovery action identifier.

Not allowed:

- access tokens;
- refresh tokens;
- authorization headers/cookies;
- provider response bodies containing credential material;
- raw exception text when it may include request/response data;
- arbitrary bridge `blocked_reason` values.

The host-only ephemeral diagnostic sink may receive only the constrained metadata defined
by `agent_core.diagnostics`; it is not a license to log provider payloads.

## 10. Operator recovery for `blocked_ambiguous`

Recovery must require explicit evidence and choose one of two mutually exclusive paths:

### A. Proven not applied

Use only when external/provider evidence proves the refresh request did not rotate/consume
the credential. CAS from the exact blocked version/attempt back to a safe refreshable
state. Any version mismatch aborts recovery.

### B. Proven applied with recovered current refresh secret

Use only when the current valid refresh secret is obtained through an approved provider
or secret-recovery channel. Store that current secret with a new generation/version using
CAS. Never infer or reconstruct it from logs or old values.

If neither condition can be proven, keep the binding blocked and require re-authentication
or account reconnection.

## 11. Backend/service availability policy

Backend unavailability must fail closed before provider work when refresh ownership or
secret state cannot be established safely.

- bounded retries may be used only for **read-only** backend operations when retrying
  cannot alter state and the overall deadline remains bounded;
- CAS writes are never blindly retried after an unknown outcome;
- provider refresh is never retried automatically after an unknown outcome;
- circuit breaking/backoff may reduce load but must not convert ambiguity into success;
- health/readiness endpoints must not expose secret values or treat `refresh_capable=True`
  as execution authorization.

## 12. Identity and least privilege

Before integration, document the exact host identity and permissions for:

- reading/updating only its own credential binding records;
- calling the specific provider refresh endpoint;
- decrypting the relevant secret values;
- emitting approved audit metadata.

The secret backend identity must not implicitly grant provider generation/write capabilities
that are unrelated to authentication refresh.

## 13. Required pre-activation tests

The real backend/exchange implementation must pass, at minimum:

- concurrent CAS claim test from multiple processes;
- stale-version conflict test;
- ambiguous backend-write test with authoritative read-back;
- crash after claim / during exchange / before commit / after commit tests;
- provider timeout and connection-reset tests;
- malformed/incomplete provider response tests;
- provider rejection test;
- refresh-token rotation test;
- revoke-during-refresh test;
- restart while `refreshing` / `blocked_ambiguous` test;
- secret/error-payload leak scan across task state, activity ledger, checkpoints, CI output
  and operator diagnostics;
- access snapshot provider/account/capability/TTL mismatch tests;
- completed-task replay test across credential rotation.

Testing a real backend may use a non-production account and isolated staging binding. It
must not require enabling general hosted task execution.

## 14. Activation sequence

Do not combine all boundaries in one deployment.

Recommended order:

1. implement concrete durable backend adapter in code with integration tests against an
   isolated staging secret namespace;
2. verify storage/CAS/failure semantics without calling a provider refresh endpoint;
3. implement real provider refresh exchange behind an explicit disabled configuration;
4. run controlled authentication-only integration tests that do not execute agent tasks;
5. review audit/redaction evidence and recovery procedure;
6. only then consider binding refreshed access credentials to a bounded read-only task;
7. long-lived host, scheduler/recurrence, provider generation/write, production prediction,
   keirin DB writes, race-data auto-fetch and report delivery remain separate approvals.

## 15. Current decision

At the time this document is added, no concrete production secret backend or real provider
refresh exchange is configured. Existing implementations and tests remain offline/fake or
provider-neutral contracts. No live hosted task execution is authorized by this document.

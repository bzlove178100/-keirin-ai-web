# Authentication and session lifecycle

This document defines how hosted agent credentials must evolve from the current manual one-shot host toward a genuinely independent long-lived host.

It does **not** enable scheduling, recurrence, provider writes, production prediction, keirin prediction DB writes, external race-data auto-fetch or report delivery.

## Current manual one-shot boundary

The manual GitHub Actions host may receive these runtime-only values:

- `SUPABASE_PROJECT_URL`;
- `SUPABASE_PUBLISHABLE_KEY`;
- `SUPABASE_OWNER_BEARER_TOKEN`;
- ephemeral `GITHUB_TOKEN`;
- exact one-run authorization values.

The values must not be committed to the repository, TaskSpec, queue/checkpoint state, activity events, artifacts or normal logs.

`tools/inspect_manual_host_config.py` performs only local structural/readiness checks. It does not authenticate to Supabase or GitHub, refresh a token, enqueue a task or execute provider actions.

A known-expired or known-too-short owner bearer session fails closed before the one-shot worker is called. An opaque token with unknown expiry may still be accepted for the bounded manual path, but expiry remains explicitly `unknown` and does not qualify the configuration for a long-lived host.

## Required long-lived host properties

Before an independent host may run unattended, authentication must move behind a refresh-capable provider boundary. The provider must expose short-lived access material to the worker without putting refresh material into task state.

Required behavior:

1. **Secret origin** — refresh/session secrets come from a dedicated runtime secret store or equivalent host-only injection, never the public repository.
2. **Least privilege** — each provider receives only the minimum scope required by its registered capability.
3. **Short-lived worker view** — task execution receives an access credential snapshot, not the durable refresh secret.
4. **Expiry awareness** — the host knows whether an access session expires and refuses to start a task when the remaining lifetime is below the configured safety margin.
5. **Single refresh owner** — only the credential provider refreshes sessions. Task runners, adapters and recovery code do not independently reauthenticate.
6. **Fail closed** — refresh failure blocks new work. It never downgrades permissions, swaps accounts or silently uses a different credential source.
7. **No ambiguous replay** — refreshing authentication after an interrupted provider action does not imply that the action may be repeated. Recovery remains governed by the task/action idempotency contract.
8. **Redacted observability** — logs and activity records may contain credential source type, expiry status and refresh outcome classification, but not token values or reusable secret fragments.
9. **Revocation** — disabling the secret source or host authorization must prevent creation of new credential snapshots. Existing queued tasks remain durable for audit/reconciliation and are not deleted to hide state.
10. **Rotation** — provider credentials can be rotated without rewriting TaskSpec fingerprints or persisted task state.

## Proposed provider interface

A future implementation should keep refresh behavior behind a narrow interface conceptually equivalent to:

```text
CredentialProvider.snapshot(required_capabilities, minimum_ttl_seconds)
  -> CredentialSnapshot

CredentialSnapshot:
  provider/account identity metadata (non-secret)
  capability scopes
  issued_at / expires_at when known
  opaque runtime access handles or in-memory values
```

The snapshot must not expose durable refresh material to task code. Provider adapters receive only the credential subset required for the current capability.

## Session state machine

Recommended states:

- `unconfigured` — no credential provider exists;
- `ready` — a valid session can be minted for the requested capability;
- `refresh_required` — current access lifetime is below the safety threshold;
- `refreshing` — one refresh operation owns the transition;
- `ready_rotated` — a new access snapshot is available;
- `blocked_auth` — refresh or authorization failed; no new provider work starts;
- `revoked` — credential source intentionally disabled.

Transitions into `blocked_auth` or `revoked` must not automatically enqueue, retry or reschedule work.

## Separation from scheduling

Authentication readiness is not permission to execute work.

Even after a refresh-capable provider exists, these remain separate gates:

- task authorization;
- capability authorization;
- queue claim/fencing;
- scheduler/recurrence enablement;
- provider write enablement;
- keirin production/DB/auto-fetch enablement;
- report-delivery enablement.

The current project keeps scheduler and recurrence OFF.

## Next implementation step

Implement a provider-neutral credential-provider interface and an in-memory/manual provider first. Add tests proving:

- no secret is serialized in safe reports;
- access expiry prevents task start below the safety margin;
- refresh is never attempted by runner/adapters directly;
- provider identity/scope mismatch fails closed;
- changing/rotating runtime credentials does not change immutable TaskSpec identity.

Do not implement a recurring worker until the refresh-capable provider and its secret-store boundary are independently validated.

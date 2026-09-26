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

## Implemented manual provider interface

`agent_core.credential_provider` provides `CredentialProvider`, `CredentialSnapshot` and `StaticInMemoryCredentialProvider`. The public package exports them and the typed boundary errors. The interface is:

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

## Static provider contract and limits

- Runtime access values are copied into memory, exposed only by explicit `secret(name)` access, and excluded from `repr` and `to_safe_dict()`. Only configured secret names and non-secret identity/scope/time metadata are reported. Errors do not echo arbitrary lookup or capability input.
- Provider/account labels, capability names and secret names must be trusted non-secret configuration. Redaction does not make putting tokens into metadata safe. Do not use generic object introspection, serialize private attributes, or log access return values.
- Required scopes must be a non-empty collection of non-blank strings and a subset of configured scopes. Malformed collections fail closed; they are not stringified or silently emptied.
- Expiry, issue time, snapshot time and minimum TTL use non-negative integer seconds; boolean, fractional and non-finite values are rejected. Future-issued, expired and insufficient-lifetime access fails closed. Equality with the minimum TTL is accepted only for an unexpired credential.
- Unknown expiry is preserved as `None`; `require_known_expiry=True` rejects it. Static credentials never advertise refresh support, even with known expiry.
- `revoke()` stops new snapshots and clears the provider's references. It does not revoke the remote token, erase Python strings, or invalidate already issued copies. A snapshot is an issuance-time view; adapters must acquire a new one immediately before an operation rather than cache it beyond its lifetime.
- One static provider must be configured for a single provider/account trust boundary, with only access values suitable for all its configured capabilities. This version returns the configured access mapping; it does not implement per-capability secret filtering. Do not inject durable refresh secrets into this mapping.
- Provider/account metadata describes host configuration, not verified remote identity. Host binding must select the intended identity. Authenticated identity checking and refresh-response identity enforcement are the next boundary.
- Runtime credentials are not TaskSpec inputs. Tests rotate an external provider while preserving the TaskSpec fingerprint and persisted state, and prove completed work is not replayed or secrets persisted.
- This module performs no network I/O, secret-store access, token refresh or host activation. It is not yet wired into the one-shot worker, and does not change its existing preflight.

## Next implementation step

Implement and validate the refresh-capable provider and host-only secret-store boundary separately:

- mint access-only snapshots; keep durable refresh material out of task runners/adapters;
- enforce configured provider/account identity and capability scope on each refresh result;
- serialize refresh ownership and define expiry/refresh/revocation transitions;
- enter `blocked_auth` on refresh failure without scheduling, retrying or replaying tasks;
- preserve TaskSpec immutable identity during credential rotation.

Do not implement a recurring worker until the refresh-capable provider and its secret-store boundary are independently validated.

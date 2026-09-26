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

Credential-provider states (implemented by the refresh boundary below):

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

## Refresh-capable access boundary

`agent_core.refresh_credentials` adds a provider-neutral `RefreshingCredentialProvider`. It implements the existing snapshot protocol using an injected `HostCredentialSource`; it is not connected to a real service or to the worker. It does not make the existing runtime preflight long-lived-ready.

The runtime layers are:

1. **HostCredentialSource** owns access to the host secret store and the provider-specific authentication exchange. Its only outward operations are `assert_available()` and `refresh_access(binding, minimum_ttl_seconds)`. There is no refresh-secret getter at the provider or adapter boundary.
2. **RefreshingCredentialProvider** owns access caching, one in-flight issuance/refresh, lifetime validation, identity/scope checks, redacted state and local revocation.
3. **CredentialSnapshot** exposes one `access_token` to the adapter. It contains no source handle or refresh material. The runner and adapter must never receive the host source itself.

`CredentialBinding` pins the trusted provider ID, stable account ID and normalized capabilities. `AccessCredentialGrant` carries only access material and known integer issue/expiry times. The response must match the entire configured identity and capability set, including rejecting added privileges. Do not bind an interchangeable account display label as a stable account ID. Remote identity verification remains a responsibility of the concrete source; comparing its returned metadata is not cryptographic identity verification.

### Refresh state behavior

| Condition | Result |
| --- | --- |
| No configured source | `unconfigured`; no snapshot |
| Configured source without cached access | `refresh_required` |
| Access missing, expired or below requested TTL | One caller enters `refreshing` |
| First valid response | `ready`, generation 1 |
| Later valid refresh | `ready_rotated`, generation incremented |
| Cached access meets TTL | Recheck source availability and lifetime; no refresh |
| Concurrent issuance/refresh already owned | Reject with `CredentialRefreshInProgress`; no second source call |
| Source failure, malformed response, identity/scope mismatch or insufficient returned TTL | Terminal `blocked_auth`; discard cached access |
| Local or source revocation | Terminal `revoked`; discard cached access and in-flight results |

Each snapshot validates source availability before issuance and after refresh. Time is rechecked after source I/O. A monotonic elapsed-time floor prevents wall-clock rollback from extending cached TTL within this process. `now_epoch` is a deterministic test override with elapsed time still counted. Unknown expiry is always rejected for refresh-capable access, even if a caller allows unknown expiry for the static provider.

`blocked_auth` and `revoked` have no automatic reset or fallback to previous access. An operator/host must remedy the source and explicitly construct a new provider. Refresh does not schedule, enqueue, retry tasks or replay provider actions. Interruptions block subsequent issuance; KeyboardInterrupt/SystemExit propagate with a fixed redacted message. Normal failures expose only fixed error classifications, with no retained original exception context in the outward error.

`refresh_capable=True` describes the implementation, not authenticated readiness or execution permission. State is evaluated on snapshot requests; a cached `ready` report is not a fresh readiness check. Local revoke prevents future issuance but cannot erase already issued Python strings or revoke a remote token. There is no cross-process lock or durable refresh state in this version.

### Host secret-store contract (not yet implemented)

A concrete source must satisfy these requirements before it can be connected:

- The host alone holds the refresh/session secret. Use a host-only secret reference scoped to one provider/account; never put refresh material or secret-store credentials into TaskSpec, adapters, checkpoint/activity state or artifacts.
- `assert_available()` must fail closed when the host authorization/secret source is disabled or its status cannot be checked. Checking an in-memory flag alone is not sufficient for a distributed secret store.
- Authenticate the provider response and map stable account identity and actual granted scopes to the pinned binding. Reject ambiguous or unverified identities. The generic provider cannot validate remote signatures or infer scopes from token text.
- Serialize refresh across every host using the same refresh secret with a secret-store version/CAS or equivalent exclusive ownership. The current provider lock protects only one object in one process. Constructing several providers over one source is not safe distributed coordination.
- Persist rotated refresh material inside the host secret store before returning access. Handle interrupted/ambiguous token rotation explicitly; do not blindly repeat a refresh request after a timeout or failed secret-store save.
- Set bounded network timeouts. The generic interface cannot cancel arbitrary Python callbacks; local revoke rejects their eventual result but does not terminate their I/O.
- Return only `AccessCredentialGrant` with an access token. Never return raw OAuth responses, durable refresh values, or provider exceptions in metadata. The generic boundary cannot identify a secret that a faulty source incorrectly labels as an access token.
- Report only fixed failure classes and non-secret configured metadata. Repr is redacted, but generic dataclass/object serialization and access-return logging are forbidden.

The tests use a fake host source only. No real refresh, secret-store read/write, source revocation, provider generation, hosted task execution or recurring worker is performed.

## Next implementation step

Implement a concrete host secret-store/exchange boundary with versioned refresh ownership, durable rotation and ambiguous-outcome handling. Validate it offline with fault injection first. Then design the adapter/runner binding that turns credential failure into a blocked task before any provider action, while keeping all execution gates OFF.

Connecting real authentication, adding host permissions, running hosted work, or enabling recurrence remains a separate explicit authorization boundary. Do not implement an always-on worker until the concrete source and recovery contract are independently validated.

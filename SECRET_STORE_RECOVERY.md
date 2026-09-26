# Versioned refresh-secret store and ambiguous-outcome recovery

This document describes the offline reference contract implemented in
`agent_core.versioned_secret_store`. It does **not** configure a production secret
store, perform a real OAuth/token refresh, activate hosted task execution, or enable a
scheduler.

## Purpose

A refresh-capable host must prevent two processes from rotating the same refresh
credential concurrently and must stop when it cannot prove whether an external refresh
or secret-store write applied.

The reference implementation adds:

- versioned refresh-secret records;
- strict compare-and-swap (CAS) writes;
- a durable `refreshing` owner state before provider exchange;
- fixed attempt IDs used as fencing/recovery evidence;
- durable rotated-secret persistence before access is returned;
- explicit `blocked_ambiguous` and `blocked_auth` states;
- read-back confirmation when a store write reports an ambiguous outcome;
- operator-only recovery for ambiguous outcomes;
- offline fault-injection tests.

## Record states

- `ready` — refresh material is available for one new version-CAS claim.
- `refreshing` — one attempt has won the current store version and may call the provider.
- `blocked_auth` — the provider definitively rejected the refresh or authentication is
  otherwise terminal for this record. No automatic retry is allowed.
- `blocked_ambiguous` — the provider or persistence outcome may have applied but cannot
  be proven. No automatic retry is allowed.
- `revoked` — refresh material is cleared and future issuance is forbidden.

The safe metadata view contains provider/account/capability identity, version,
generation, state, attempt identifiers and fixed failure classes. It never contains the
refresh secret.

## CAS ownership

The store contract is:

```text
read(binding) -> RefreshSecretRecord
compare_and_swap(binding, expected_version, replacement(version=expected+1))
  -> RefreshSecretRecord
```

Only the writer holding the observed version can move `ready -> refreshing`. A stale
writer receives `SecretStoreConflict` and must not contact the provider.

The included `InMemoryVersionedSecretStore` exists only to prove semantics and inject
failures. A real host must provide equivalent durable/atomic semantics from its secret
store or database.

## Refresh sequence

1. Read the exact pinned provider/account/capability record.
2. CAS `ready -> refreshing`, recording a unique attempt ID.
3. Call the provider exchange exactly once for that attempt.
4. Validate returned provider/account/capabilities and access/refresh material.
5. CAS the rotated refresh secret to `ready`, incrementing refresh generation.
6. Read-back/confirm ambiguous store writes.
7. Only after durable confirmation return the access-only grant to
   `RefreshingCredentialProvider`.

The runner/adapter still receives only `CredentialSnapshot` access material. It never
receives the store, exchange object, or refresh secret.

## Ambiguous provider result

Any provider/transport exception that is not explicitly typed as a definite rejection
is treated as ambiguous. Examples include timeout, connection loss after request send,
process interruption, malformed success payload and incomplete rotated-secret data.

The source attempts to persist:

```text
state = blocked_ambiguous
last_attempt_id = <attempt>
failure = <fixed classification>
```

The source then fails closed. It does not repeat the exchange, fall back to the old
refresh secret, downgrade scopes, switch accounts, enqueue a task, or resume provider
actions.

## Ambiguous secret-store write

A store adapter may report `SecretStoreAmbiguousWrite` when it cannot tell whether a CAS
committed.

The source performs a read-back:

- if the exact expected attempt/version/generation is present, the write is accepted as
  confirmed;
- if the record still shows this attempt as `refreshing`, it is moved to
  `blocked_ambiguous` when possible;
- otherwise the operation fails closed as persistence ambiguity/conflict.

No generic blind retry is permitted.

## Recovery

Recovery requires external evidence and an exact blocked record version + attempt ID.
It is never automatic.

### Confirmed not applied

Use `recover_ambiguous_not_applied(...)` only after the operator/provider can prove the
refresh did not apply. The same stored refresh secret returns to `ready` with a new CAS
version.

### Confirmed applied with recovered rotated secret

Use `recover_ambiguous_with_rotated_secret(...)` only after the operator/provider can
prove the refresh applied and can supply the correct rotated refresh secret through the
host-only recovery path. The recovered secret becomes `ready`, generation increments,
and the version advances.

Recovery does not make an existing `RefreshingCredentialProvider` instance ready again.
A provider instance that entered terminal `blocked_auth` remains blocked. After the
secret record is reconciled, the host must explicitly construct a new provider instance.

## Revocation

`revoke()` uses CAS to enter `revoked`, clears the store's reference to refresh material,
and prevents future source availability/refresh. This does not claim remote provider
revocation or secure memory erasure.

## Remaining production boundary

Before live long-lived authentication can be considered, a concrete secret-store and
provider-exchange implementation must still prove:

- real cross-process atomic CAS/fencing;
- host-only secret encryption/access policy;
- provider identity and granted-scope verification;
- bounded network timeouts;
- durable recovery evidence after process crash;
- safe rotation of the store's own authentication/credentials;
- redacted logs/metrics;
- explicit operator recovery tooling and audit events.

No live execution, scheduler, recurrence, prediction write, external keirin data fetch,
generation-provider execution, or report delivery is enabled by this reference module.

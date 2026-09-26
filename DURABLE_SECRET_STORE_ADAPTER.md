# Durable secret-store adapter contract

`agent_core.durable_secret_store` defines the boundary between the already tested
versioned refresh state machine and a future durable host-only secret backend.

It does **not** configure a production secret manager/database, migrate Supabase, call a
real OAuth/token refresh endpoint, enable hosted execution or start a scheduler.

## Backend requirements

A concrete backend must implement two operations:

```text
read(opaque_binding_key) -> record | none
compare_and_swap(opaque_binding_key, expected_version, replacement) -> committed record
```

`compare_and_swap` must be atomic across host processes. Its outcome classifications are
part of the safety contract:

- `DurableSecretBackendConflict` — stale version definitely did **not** apply;
- `DurableSecretBackendAmbiguousWrite` — the backend cannot prove whether the write
  committed;
- `DurableSecretBackendUnavailable` — backend is unavailable and no stronger outcome
  statement is available.

Provider/database-specific exception messages are not propagated. The adapter maps them
to fixed secret-store errors outside the original exception handler to avoid retaining a
secret-bearing error object in outward exception context.

## Record key and schema

The backend key is a SHA-256 digest of the pinned provider/account/capability binding.
Raw provider/account labels are not placed into the storage key.

The stored value uses schema:

`credential-refresh-secret-record-v1`

It includes the refresh secret because the durable host backend must retain that secret.
This payload is **host-only** and is not a safe logging/reporting structure.

The adapter validates on every read and CAS read-back:

- schema version;
- exact provider/account/capability binding;
- non-negative version/generation;
- refresh state and attempt-ID rules through `RefreshSecretRecord`;
- fixed failure classifications;
- exact CAS read-back equality.

Corrupt/mismatched records fail closed.

## Relationship to the refresh source

`DurableVersionedSecretStore` implements the same `VersionedSecretStore` contract used
by `VersionedHostCredentialSource`.

Therefore the existing source still owns:

- `ready -> refreshing` CAS claim before provider contact;
- attempt fencing;
- one exchange attempt per claim;
- rotated-secret persistence before access return;
- ambiguous write read-back;
- `blocked_auth` / `blocked_ambiguous`;
- explicit operator recovery;
- revocation.

The backend adapter does not retry provider operations or secret writes.

## What a real backend still must prove

Before any live durable secret integration:

1. atomic CAS under multiple processes;
2. encryption at rest and host-only access control;
3. no secret-bearing query/error logging;
4. durable write/read behavior across process/region failures;
5. bounded network timeouts;
6. deterministic conflict vs ambiguous-write classification;
7. credential rotation for the backend itself;
8. backup/recovery policy that does not silently restore stale refresh material;
9. audit metadata without refresh-secret values;
10. explicit operator procedure for `blocked_ambiguous` recovery.

The included tests use a fake in-memory backend with injected conflict, ambiguous-write,
unavailable, corrupt-read and incorrect-readback failures. Passing those tests validates
the adapter contract only, not a production backend.

## Activation boundary

Connecting a real secret store or provider refresh remains a separate integration and
security boundary. No live hosted task execution, scheduler/recurrence, production
prediction, keirin prediction DB write, race-data auto-fetch, generation-provider write,
or report delivery is enabled by this module.

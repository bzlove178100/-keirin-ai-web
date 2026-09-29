# Staging secret backend: Vault with transactional version fencing

Reviewed: 2026-09-29 (Asia/Tokyo).
Status: **candidate selected; synthetic stack qualified through PR #131; review-only migration package prepared; real-secret activation blocked**.

This is the concrete follow-on to `REAL_AUTH_INTEGRATION_REQUIREMENTS.md`. It selects
a candidate and specifies its implementation boundary. It does not create roles,
change grants, store secrets, deploy a function, or authorize a provider refresh.

The current migration-planning boundary is documented in
`STAGING_SECRET_BACKEND_MIGRATION_REVIEW.md`. That package is review-only; no real Vault
migration, host login, password, refresh credential or provider binding has been applied.

## 1. Decision and evidence

Prototype **Supabase Vault plus a private PostgreSQL metadata table**, accessed by a
dedicated host database identity. Use one database transaction for every version
transition and associated encrypted-secret update.

This is an engineering choice: the existing project already uses PostgreSQL, and keeping
the secret and fencing metadata in the same database avoids a two-service commit protocol.
It is not a claim that the existing project is ready to hold agent refresh credentials.

Alternatives considered:

| Candidate | Decision |
| --- | --- |
| Test SQLite backend from PR #97 | Keep for synthetic tests only; it has no encryption/access control. |
| Vault + private PostgreSQL metadata | Prototype candidate, subject to the blockers below. |
| External managed secret store + separate metadata database | Reconsider if Vault cannot meet key lifecycle/isolation requirements; requires its own atomicity and service selection review. |
| Application-managed encryption in PostgreSQL | Deferred; would add a host key custody and rotation implementation. |

Official Vault documentation describes encrypted storage, a decrypted view, encrypted
backups/replication, and a project key managed separately from database data. It also
warns that access to the decrypted view permits reading plaintext. [S1]

### Read-only staging observations

Catalog checks on the authorized staging project at the 2026-09-27 review found:

| Observation | Result |
| --- | --- |
| PostgreSQL server version | `17.6` |
| `supabase_vault` extension | `0.3.1` |
| `anon` / `authenticated` SELECT on `vault.secrets` and `vault.decrypted_secrets` | false |
| `service_role` SELECT on those two objects | true |
| `anon` / `authenticated` EXECUTE on `vault.create_secret` and `vault.update_secret` | false |
| `service_role` EXECUTE on those functions | true |
| Those two Vault functions use SECURITY DEFINER | true |

These are object privileges, not a complete exploitability assessment. Schema access,
inherited roles, API exposure and other functions also matter. No Vault rows, names,
values, keys or counts were read. `ops/credential_vault_inventory.sql` is the repeatable
catalog-only inventory for subsequent reviews; it is not a readiness certificate.
`ops/staging_secret_backend_preflight.sql` now adds a broader review-only catalog/config
inventory for the next evidence refresh. Neither query authorizes a migration.

The observed service-role access fails this design's dedicated-host isolation target.
Do not store agent refresh secrets in this Vault until effective access is restricted
and regression-tested. Review dependencies before changing project-wide Vault grants.
If those grants cannot safely be restricted, use a separately approved isolated backend.

The changelog announces a PostgreSQL minor-version rollout after the observed version.
Recheck supported patch level and relevant upgrade prerequisites before activation;
this design does not upgrade the project or claim it is affected by a specific defect. [S6]

## 2. Host identity and private boundary

Proposed names below are design identifiers, not deployed objects.

- `agent_credential_private`: schema excluded from Data API exposure and Realtime.
- `agent_secret_host`: dedicated LOGIN role with no superuser, BYPASSRLS, role creation,
  database creation, replication, schema creation or privileged role membership.
- `agent_secret_broker`: NOLOGIN function owner with only reviewed Vault and metadata
  permissions. It must not own unrelated objects or be usable via SET ROLE by the host.
- A separate operator identity provisions bindings, changes access mappings and performs
  evidence-based recovery. Runtime functions cannot provision or recover bindings.

The host receives USAGE on the private schema and EXECUTE on exact read/CAS function
signatures. It receives no direct Vault/table access. Revoke PUBLIC execution on each
new function in the same transaction that creates it and set matching default privileges.
Browser/API roles, `authenticator`, and `service_role` receive no access to this boundary.
Supabase documents roles/grants and warns that functions are executable broadly by
default unless privileges are restricted. [S2, S3]

Narrow SECURITY DEFINER functions are proposed because granting the runtime caller
direct access to Vault's decrypted view would expose other bindings. This is a deliberate
privilege boundary, not a workaround for a failed query. Require:

1. Fixed safe `search_path`, fully qualified object names and no dynamic SQL.
2. A protected mapping from **session_user** to allowed binding keys; never accept a
   caller-supplied owner or JWT claim as authority.
3. An explicit `auth.uid()` check rejecting non-null JWT identity, plus the database-login
   allowlist. A null `auth.uid()` alone never authorizes access. This path uses direct
   database authentication, not a browser JWT or PostgREST session.
4. RLS on private metadata/mapping tables, explicit broker policies, and tests for role
   switching, unauthorized binding access, direct Vault access and all function overloads.
5. No broad function/table grants introduced to make a test pass.

Administrative/platform roles remain part of the trust boundary. Document their effective
access instead of claiming that SQL ACLs isolate secrets from database administrators.

The host uses a verified primary database endpoint, TLS certificate/hostname verification,
bounded connections and timeouts. A session pooler can be evaluated separately if direct
connectivity is unavailable; session identity must be demonstrated with the actual mode.
Do not route authoritative read-back to replicas or rely on cached state. [S4]

The database login credential is a bootstrap secret held outside this database by the
approved host secret facility. Its provisioning/rotation is still unresolved. Never put
the project administrator password or service-role API key into this adapter.

## 3. Record layout and atomic CAS

Use a private metadata row keyed by the existing opaque binding key. Store exact schema,
provider/account/capability binding, version, state, generation, attempt identifiers,
fixed failure classification and an optional Vault secret reference. The refresh value
exists only in Vault and transient host memory. Vault names/descriptions contain no identity,
token or provider payload. A raw secret identifier is never accepted from a runtime caller.

Do not hard-code the hosted Vault secret-reference type from the historical observation.
The next catalog preflight must confirm the current extension schema and function signatures
before exact migration DDL is drafted.

Enforce uniqueness of the metadata binding and non-null Vault reference; one Vault entry
must not be shared across bindings. Enforce integer ranges, field allowlists and state
invariants matching `RefreshSecretRecord`; reject unknown/extra secret-bearing fields.
The SQL bigint range needs an explicit adapter limit because Python integers are unbounded.

`read(binding_key)` must return metadata and its decrypted value from one database snapshot.
Do not read metadata and then Vault in separate unlocked statements. Reconstruct the raw
`DurableSecretBackend` record only in the private function/host result; never in an audit row.

`compare_and_swap(key, expected_version, replacement)` uses this short transaction:

1. Authenticate the session and validate the allowed binding and replacement schema.
2. Lock exactly that binding's metadata row with SELECT FOR UPDATE.
3. Compare the locked version. Missing/stale state returns a fixed no-write conflict.
4. Validate `replacement.version = expected_version + 1`, immutable identity and state
   invariants. Check for exhausted integer range before mutation.
5. Update the mapped Vault value and metadata together. Clearing a secret deletes the
   mapped Vault row and clears its reference atomically. Provisioning is a separate path.
6. Construct the strict result, commit, then allow the adapter to report success.

All mutations for a binding, including revocation and operator recovery, take the same
metadata lock first. No provider/network call runs while a database lock is held. The
claim transaction must finish before refresh I/O; the rotated-secret commit is a second
transaction after a validated response. PostgreSQL's row-lock/update behavior supports
serializing contenders; this design still requires real-backend concurrency tests. [S5]

No function returns an access token. A local function result received before transaction
commit is not durability evidence. No automatic upsert or fallback insert is allowed.

## 4. Failure classification and recovery

| Evidence available to the adapter | Outward classification |
| --- | --- |
| Authenticated fixed conflict response proving no write | `DurableSecretBackendConflict` |
| Connection/setup failure before any write request can be sent | `DurableSecretBackendUnavailable` |
| Server rejection with verified transaction rollback | Fixed unavailable/validation error, never a stale-version conflict |
| Write may have been submitted; timeout, disconnect, lost commit response or malformed result | `DurableSecretBackendAmbiguousWrite` |
| Read failure or malformed read result | Fixed unavailable/integrity error |

No raw SQL/driver exception, DETAIL, HINT, statement parameters or connection string escapes
the transport. Raise fixed errors after leaving exception handlers so raw exceptions are
not retained as outward context. Disable automatic write retries in every client layer.

After ambiguity, the existing source/store performs authoritative read-back and checks the
exact version/attempt/record. It must not retry a CAS or provider refresh on its own.
`refreshing` and `blocked_ambiguous` survive process restart. Revocation cannot be undone
by a stale refresh commit. Backup restore must start with provider use disabled: restored
versions may refer to already-consumed tokens, so normal restart logic is insufficient.

## 5. Encryption, logs and operational blockers

Before any real credential is provisioned, provide evidence for each item:

| Gate | Required evidence | Current status |
| --- | --- | --- |
| Effective host isolation | ACL/membership tests and denied reads/calls for API roles and other bindings; reviewed existing Vault dependencies | Blocked by observed service-role privileges; refresh evidence before migration DDL |
| Root key lifecycle | Supported key rotation/re-encryption, rollback and compromise procedure, with a synthetic rehearsal | Unverified |
| Backup/restore | Same-project and cross-project recovery procedure; old refresh values never silently resume | Unverified |
| Bootstrap host credential | Approved host facility and rotation procedure; no repository/CI-output exposure | Unconfigured |
| Logging and telemetry | Synthetic canary scan of SQL statements, bind parameters, errors, audit logs, tracing and host output | Synthetic local/container evidence exists; real platform custody unverified |
| Target runtime | Supported patched Postgres/extension versions, verified TLS endpoint and stable session identity | Historical versions observed; fresh staging inventory required |
| Atomicity and faults | Two real sessions/processes, rollback between Vault and metadata changes, lost commit acknowledgement, restart and revoke races | Synthetic PostgreSQL/app stack qualified; unverified for hosted Vault |

Vault key portability documented by Supabase does **not** establish a safe in-place key
rotation procedure. Copying/replacing a root key is not a substitute for re-encryption.
Do not export a root key through ChatGPT tools or store one in repository artifacts. [S1]

Use bound SQL parameters, but do not assume parameterization prevents telemetry leaks.
Verify the actual PostgreSQL/driver/audit configuration, including error parameter logging.
Metadata-only audit events contain fixed states/classifications and bounded identifiers.
No secret-bearing result sets may enter CI output or durable task/activity persistence.

Deletion cannot prove erasure of old encrypted backups. Document retention and administrator
access, and treat provider-side revocation as a separate, confirmed operation.

## 6. Implementation sequence and acceptance

The original local implementation slice is now complete at the **synthetic** boundary.
Repository evidence through PR #131 includes full refresh-record validation, independent
PostgreSQL CAS behavior, bounded host adapter/process deadlines, verify-full TLS, strict
bootstrap lease fencing, hardened-container composition, fail-closed trust/lease/hostname
negative cases and a real row-lock/process-deadline ambiguity case. This does not certify
hosted Vault encryption, grants, key lifecycle, platform logs or a real bootstrap facility.

Next sequence:

1. Review `STAGING_SECRET_BACKEND_MIGRATION_REVIEW.md` and the read-only
   `ops/staging_secret_backend_preflight.sql`. Merge review artifacts only after normal CI;
   merging them does not authorize any live staging action.
2. Obtain a fresh **read-only** staging catalog/configuration inventory before drafting DDL.
   Confirm current PostgreSQL/Vault versions, exact Vault function signatures/owners,
   effective role memberships/privileges, proposed-name conflicts and Data API exposure.
3. Based on that evidence, prepare a separate timestamped migration PR with exact role,
   schema, table, policy, function, grant/revoke and rollback SQL. Do not auto-apply it and
   include no password or real secret.
4. Only after explicit staging-apply authorization, apply that reviewed DDL with no secret
   rows and run identity/ACL/catalog checks.
5. In a separate phase, use synthetic hosted Vault values to prove real-backend concurrency,
   rollback, ambiguous-write, restart and revoke behavior before any real credential.
6. Close the operational gates, then separately consider real credential provisioning and
   authentication-only refresh tests. Hosted tasks, scheduler, provider generation/write
   and reports remain separate activation boundaries under
   `REAL_AUTH_INTEGRATION_REQUIREMENTS.md`.

### Current synthetic SQL/ACL evidence

`tests/support/vault_postgres_contract.sql` and the associated contract cases remain a
**synthetic fixture**, not deployable migration SQL. The fixture now models the complete
refresh-record field set, dedicated host identities, per-binding mapping, denied direct
Vault/table access, strict replacement validation, row locking, stale CAS, rollback/fault
behavior and revocation using `SYNTHETIC:` values only.

The co-resident hardened application tests use that private contract to exercise the actual
application stack. They deliberately do not prove Supabase Vault encryption, real hosted
function signatures, hosted ACLs, root-key handling, provider refresh semantics or final
production psycopg/libpq packaging.

Existing PR #97 SQLite evidence applies only to that test backend.

## Sources checked

- S1: https://supabase.com/docs/guides/database/vault
- S2: https://supabase.com/docs/guides/database/postgres/roles
- S3: https://supabase.com/docs/guides/database/functions
- S4: https://supabase.com/docs/guides/database/connecting-to-postgres
- S5: https://www.postgresql.org/docs/17/transaction-iso.html
- S6: https://supabase.com/changelog/postgres-15-19-17-11-breaking-changes

Source facts are distinguished above from proposed design requirements. Live catalog
observations are point-in-time results, not guarantees about future project configuration.

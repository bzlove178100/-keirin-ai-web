# Staging secret-backend migration review package

Reviewed: 2026-09-29 (Asia/Tokyo)
Status: **review only — do not apply**

This package turns the design in `STAGING_SECRET_BACKEND_DESIGN.md` into a bounded staging
migration plan. It intentionally does **not** add a file under `supabase/migrations`, create
or alter any database object, change a grant, provision a database password, write a Vault
row, bind a provider credential, deploy a function, dispatch a workflow, or enable hosted
task/provider execution.

The current verified functional base is PR #131 plus the documentation sync in PR #132.
All production prediction, prediction DB writes, external race-data fetching, hosted task
execution, provider generation/write, scheduler/recurrence and live report delivery remain
disabled.

## 1. Review decision

The candidate remains **Supabase Vault plus private PostgreSQL metadata**, with one database
transaction fencing each version transition and secret mutation.

This is not yet approved for real refresh credentials. Before any migration is applied, the
operator must refresh the catalog evidence and resolve the existing isolation blocker noted
in `STAGING_SECRET_BACKEND_DESIGN.md`: the last observed staging state granted
`service_role` access to Vault objects/functions. That state does not meet the dedicated-host
isolation target.

Do not solve that blocker by blindly revoking project-wide Vault privileges. First identify
all dependencies. If the required isolation cannot be established without breaking another
supported path, select a separately isolated secret backend instead.

## 2. Exact scope of a later migration

A separately approved migration may create only the following boundary:

- private schema: `agent_credential_private`;
- runtime database login: `agent_secret_host`;
- NOLOGIN function owner: `agent_secret_broker`;
- private binding metadata table keyed by the existing opaque
  `DurableVersionedSecretStore.key_for(...)` value;
- private mapping table from `session_user` to allowed binding keys;
- narrow `read_binding(text)` and `cas_binding(text,bigint,jsonb)` functions;
- the minimum Vault privilege required by the broker after the exact hosted Vault function
  signatures and ownership are re-inventoried;
- explicit revocation of PUBLIC access on every new private function and matching default
  privileges for future objects in the private schema.

The later migration must **not** create a provider account binding, insert a refresh secret,
store an OAuth client secret, enable a provider refresh exchange, or configure a worker.
Provisioning is a later, separately approved step.

## 3. Metadata contract

The private metadata row must preserve the current `RefreshSecretRecord` contract:

| Field | Migration requirement |
| --- | --- |
| `binding_key` | non-empty opaque primary key; never a raw provider/user identifier |
| `schema_version` | exactly `credential-refresh-secret-record-v1` |
| `provider_id` / `account_id` | immutable after provisioning |
| `capabilities` | non-empty, no null values, immutable after provisioning |
| `version` | PostgreSQL bigint, non-negative, explicit exhaustion guard |
| `state` | only `ready`, `refreshing`, `blocked_auth`, `blocked_ambiguous`, `revoked` |
| `refresh_generation` | non-negative bigint |
| `active_attempt_id` / `last_attempt_id` | bounded log-safe identifiers only |
| `failure` | fixed allowlisted classification only |
| Vault reference | unique per binding; absent when revoked |

The refresh value exists only in Vault and transient host memory. Vault names/descriptions
must not contain provider account identity, token fragments, task data, email addresses or
other credential payload.

The exact Vault secret-id column type is intentionally **not hard-coded in this review**.
`ops/staging_secret_backend_preflight.sql` must first confirm the current hosted catalog.
Likewise, no Vault function signature is assumed from an older extension version.

## 4. Role and grant model

### `agent_secret_host`

Required attributes for the later role:

- LOGIN;
- NOSUPERUSER;
- NOCREATEDB;
- NOCREATEROLE;
- NOREPLICATION;
- NOBYPASSRLS;
- no membership in `service_role`, `postgres`, privileged extension-owner roles or the
  broker role;
- no direct SELECT/INSERT/UPDATE/DELETE on private metadata, mapping tables, Vault tables
  or decrypted Vault views;
- only USAGE on `agent_credential_private` plus EXECUTE on the exact read/CAS signatures.

The login password is a bootstrap credential and must not be embedded in the migration,
repository, GitHub Actions configuration, Edge function source, task input or activity log.

### `agent_secret_broker`

Required attributes:

- NOLOGIN;
- NOSUPERUSER;
- NOCREATEDB;
- NOCREATEROLE;
- NOREPLICATION;
- NOBYPASSRLS;
- owner of only the reviewed private functions;
- only the minimum metadata/mapping privileges and exact Vault function/table privileges
  established by the refreshed catalog review;
- not grantable to the runtime host role.

### Browser/API roles

`PUBLIC`, `anon`, `authenticated`, `authenticator` and `service_role` receive no USAGE or
EXECUTE on `agent_credential_private` objects created for this boundary. Existing platform
roles remain part of the broader administrative trust boundary and must be documented
accurately rather than claimed away by SQL ACLs.

## 5. Function safety requirements

Both runtime functions must be `SECURITY DEFINER` with a fixed safe `search_path` and fully
qualified object references. They must contain no dynamic SQL.

Each call must fail closed unless all of the following are true:

1. `auth.uid()` is null;
2. `session_user` is the direct approved host login;
3. the host-to-binding mapping permits the exact opaque binding key;
4. the current metadata row passes the complete schema/state invariant set;
5. the Vault reference resolves through the broker's reviewed minimum privilege path.

`cas_binding` additionally must:

- lock exactly the target metadata row with `FOR UPDATE`;
- return a fixed conflict only when a stale/missing version proves no write occurred;
- require `replacement.version = expected_version + 1`;
- preserve provider/account/capability identity;
- update Vault value and metadata in one transaction;
- delete/clear the Vault value atomically on terminal revocation;
- perform no provider/network I/O while the database row lock is held;
- never upsert or insert a missing runtime binding as a fallback.

Any timeout/disconnect after a write may have been submitted remains an ambiguous write.
No client layer may automatically replay the CAS.

## 6. Bootstrap credential ownership and lifecycle

The database login credential for `agent_secret_host` must be owned by a host secret
facility outside the target database. Before activation, document all of the following:

- provisioning actor and approval path;
- storage facility and access policy;
- version identifier carried into `BootstrapPasswordLease`;
- rotation interval and maximum overlap window;
- procedure for marking the old version not-current before/at cutover;
- emergency revocation procedure;
- evidence that repo, workflow logs, process command lines, environment dumps, crash dumps
  and durable diagnostics do not receive the password;
- recovery behavior when the host observes stale, expired or revoked lease material.

Rotation must use a new lease version and fail closed on old-version reuse. Revocation must
not depend on worker restart.

## 7. TLS trust and pin lifecycle

A later live profile must pin one approved primary database endpoint and retain verify-full
TLS. Before migration activation, record:

- expected DNS hostname;
- reviewed address/endpoint class;
- CA source and SHA-256 used by `StrictPostgresConnectionFactory`;
- CA validity/renewal owner;
- procedure for dual-reviewing a CA/hostname change;
- rollback path if a trust update fails;
- evidence that ambient libpq/OpenSSL variables cannot override the profile.

A DNS, CA or endpoint change is a configuration/security change, not a transparent retry
condition. Wrong hostname/trust must continue to fail closed as qualified in the synthetic
co-resident tests.

## 8. Migration phases

### Phase A — refreshed read-only inventory

Run only catalog queries. Do not read Vault rows, values, names, keys or counts.

Required artifacts:

- output of `ops/credential_vault_inventory.sql`;
- output of `ops/staging_secret_backend_preflight.sql`;
- exact PostgreSQL and `supabase_vault` versions;
- exact Vault function signatures/owners/security-definer state;
- effective object/schema/function privileges for API/platform roles;
- proposed role-name conflict check;
- dependency review for any proposed Vault grant change.

Any unexpected function overload, owner, inherited membership, schema exposure or platform
role access is a stop condition until reviewed.

### Phase B — migration DDL review

Only after Phase A is reviewed, produce the actual timestamped SQL migration. The migration
must be reviewed as a distinct PR and must still contain **no secret data**.

The migration PR must show exact `CREATE ROLE/SCHEMA/TABLE/FUNCTION/POLICY`, owner changes,
revoke/grant statements and rollback SQL. It must not be auto-applied by merge.

### Phase C — explicitly authorized staging apply

Requires a new explicit approval after the exact migration SHA and refreshed preflight are
known. Apply only the reviewed DDL. Do not provision a real credential in the same step.

After application, run catalog/ACL/session-identity checks with no secret rows present.

### Phase D — synthetic hosted Vault qualification

Only after Phase C evidence is accepted, insert clearly synthetic non-provider markers into
an isolated binding and run multi-session CAS, rollback, ambiguous-write, revoke and restart
checks. Delete the synthetic material after evidence capture.

### Phase E — real credential provisioning

Out of scope for this review package. Requires separate approval plus closure of encryption
key lifecycle, backup/restore, log custody, bootstrap-secret custody and provider recovery
gates.

## 9. Rollback design

Before any real secret exists, rollback is structural:

1. disable/revoke host EXECUTE on private functions;
2. verify no active host session and no binding rows;
3. remove host mappings;
4. remove private functions/policies/tables/schema in dependency order;
5. remove dedicated roles only after membership/ownership checks prove they are unused;
6. restore only Vault grants that were explicitly changed by the reviewed migration and
   whose prior state was captured in Phase A.

Do not use `CASCADE` as a convenience rollback mechanism.

Once any real refresh credential has ever been provisioned, rollback is no longer merely
DDL cleanup. Provider-side revocation/reconnection, local quarantine and backup-retention
handling become mandatory. An old encrypted backup cannot be treated as safely erasable or
refresh-capable merely because current rows were deleted.

## 10. Post-apply observation plan

A staging apply is accepted only after evidence shows:

- direct host login and expected database/session identity;
- primary/read-write connection;
- exact TLS hostname/CA verification;
- host has no direct private-table/Vault access;
- host can execute only exact read/CAS functions;
- other binding access is denied;
- API/browser roles cannot use the private boundary;
- unexpected role switching fails;
- no private schema is exposed through the Data API configuration;
- SQL/audit/host logs contain no synthetic secret marker or bind value;
- fixed outward classifications remain unchanged;
- no hosted task/provider execution was enabled as a side effect.

The observation step must not claim isolation from database/platform administrators.

## 11. Acceptance blockers

The following remain hard blockers to provisioning a real refresh credential:

- unresolved `service_role`/Vault effective access or unreviewed dependency impact of
  changing it;
- unverified Vault root-key rotation/re-encryption/compromise procedure;
- unverified backup/restore behavior for refresh-chain safety;
- no approved external bootstrap-password facility and rotation/revocation procedure;
- unqualified platform/host log, trace and administrator custody;
- no final production packaging/provenance for the intended psycopg/libpq native stack;
- unreviewed live endpoint/DNS/CA lifecycle;
- missing real-backend multi-process CAS/fault evidence.

Passing this review PR closes none of those blockers by itself.

## 12. Explicit non-authorization

Merging this file or the read-only preflight SQL means only that the **migration plan is
available for review**. It is not authorization to:

- apply a database migration;
- alter Vault or role grants;
- create a database login/password;
- store or migrate a real secret;
- call a provider refresh endpoint;
- run a hosted task;
- enable scheduler/recurrence;
- enable provider generation/write;
- enable production prediction or prediction DB writes;
- enable external race-data fetching;
- enable live report delivery.

Each later boundary requires its own explicit decision and verified evidence.

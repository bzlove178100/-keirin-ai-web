# Staging secret backend Phase B DDL review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — blocked from apply**

This review follows the fresh Phase A evidence in
`STAGING_SECRET_BACKEND_PHASE_A_EVIDENCE.md`. It converts the current contract into exact
candidate DDL and rollback files without placing either under `supabase/migrations` and
without applying them to staging.

Files in this review:

- `review/staging_secret_backend_phase_b_candidate.sql` — forward candidate;
- `review/staging_secret_backend_phase_b_rollback.sql` — structural rollback candidate.

Neither file contains a password, provider credential, refresh secret, binding row, task
payload or production identifier.

## 1. Current blocker and official-platform review

The fresh staging inventory confirmed that `service_role` currently has direct Vault
schema/relation/function privileges, including SELECT on `vault.decrypted_secrets`.
Therefore the shared staging Vault still fails the dedicated-host isolation target.

The current Supabase Vault documentation explicitly warns that anyone with access to
`vault.decrypted_secrets` can access decrypted secrets and says access must be protected
with appropriate SQL privileges. The current API-key documentation also states that
`service_role` bypasses RLS, while table/object grants are still evaluated first and a
missing grant can deny `service_role` before RLS is considered.

Those facts show that SQL ACLs are relevant to `service_role`; they do **not** establish
that removing the platform's current Vault grants is a supported, dependency-free hosted
configuration. The reviewed official pages do not provide a documented migration procedure
that guarantees the current Vault `service_role` grants may be revoked without affecting
platform or external consumers.

Accordingly this Phase B candidate does **not** revoke any existing `service_role` Vault
grant. Instead, its first transaction guard aborts if those sensitive privileges are still
present. On the current staging state the candidate is intentionally non-applicable.

Sources reviewed:

- https://supabase.com/docs/guides/database/vault
- https://supabase.com/docs/guides/getting-started/api-keys
- https://supabase.com/docs/guides/api/securing-your-api

## 2. Fresh function-definition evidence

A metadata-only Phase A follow-up inspected the hosted definitions of the two public Vault
mutation functions. No Vault row or value was read.

Observed on staging `supabase_vault 0.3.1`:

- `vault.create_secret(new_secret text, new_name text DEFAULT NULL,
  new_description text DEFAULT '', new_key_id uuid DEFAULT NULL) -> uuid`;
- `vault.update_secret(secret_id uuid, new_secret text DEFAULT NULL,
  new_name text DEFAULT NULL, new_description text DEFAULT NULL,
  new_key_id uuid DEFAULT NULL) -> void`.

Both are `SECURITY DEFINER`, owner `supabase_admin`, with an empty function `search_path`.
The observed `update_secret` implementation leaves name/description unchanged when those
arguments are null. The candidate runtime CAS therefore calls the exact hosted update
signature with only the id and new secret semantically populated.

`create_secret` is deliberately **not** granted to the runtime broker. Provisioning is a
separate operator boundary and remains out of scope.

## 3. Candidate security model

The forward candidate is fail-closed and starts inside one transaction. Before creating
anything it verifies the reviewed PostgreSQL/Vault shape, proposed-name absence and the
absence of the known `service_role` Vault-access blocker. Any mismatch raises a fixed
exception before DDL.

If a future explicitly approved environment passes that guard, the candidate would create:

- `agent_secret_host`: LOGIN with no password, no superuser/role/db/replication/BYPASSRLS
  power and no privileged memberships;
- `agent_secret_broker`: NOLOGIN with the same privilege restrictions;
- private schema `agent_credential_private`;
- `bindings` and `host_bindings` metadata tables with RLS + FORCE RLS;
- exact `read_binding(text)` and `cas_binding(text,bigint,jsonb)` SECURITY DEFINER
  functions with fixed `search_path` and fully-qualified object names.

The host receives only private-schema USAGE plus EXECUTE on the two exact functions. It
receives no direct table or Vault access.

The broker receives only what the two runtime functions require:

- private metadata SELECT/UPDATE under forced RLS;
- `auth.uid()` execution for JWT-session rejection;
- Vault schema USAGE;
- SELECT on `vault.decrypted_secrets` for the mapped secret read;
- DELETE on `vault.secrets` for terminal revocation;
- EXECUTE on the exact `vault.update_secret(uuid,text,text,text,uuid)` signature.

It does not receive `vault.create_secret`, direct crypto-helper EXECUTE, INSERT on Vault or
provider/network capability.

## 4. Runtime invariants

`read_binding` rejects any call unless:

1. `session_user` is exactly `agent_secret_host`;
2. `auth.uid()` is null;
3. the protected host-to-binding mapping contains the exact opaque binding key.

`cas_binding` applies the same caller checks, locks the metadata row with `FOR UPDATE`,
requires the exact expected version, validates the full replacement JSON shape and fixed
state/failure classifications, preserves provider/account/capability identity and rejects
version exhaustion.

A non-revoked replacement requires a non-empty refresh value. A terminal `revoked`
replacement requires a JSON null refresh value. Vault update/delete and metadata mutation
occur in the same PostgreSQL transaction. There is no provider/network I/O and no retry,
upsert or missing-binding fallback inside the SQL function.

The candidate returns fixed SQLSTATE/classification strings and does not include submitted
secret text in error messages.

## 5. Why the candidate is not under `supabase/migrations`

The current staging environment fails the guard by design because the shared Vault is not
yet isolated from `service_role`. Placing this file in the migration path would blur the
boundary between review and authorization and could make a future deployment mechanism
mistake the review artifact for approved DDL.

Moving an exact reviewed file into `supabase/migrations` is a separate future change only
after:

- the Vault isolation decision is explicitly resolved;
- a fresh preflight still matches the pinned function/object shape;
- bootstrap-password custody and rotation are approved;
- migration SHA and rollback are reviewed;
- the user explicitly authorizes the staging-apply boundary.

## 6. Rollback scope

The rollback candidate is structural and is valid only before any real credential is ever
provisioned. It first revokes host execution, requires no active `agent_secret_host`
session and requires both private tables to contain zero rows. It then drops exact
functions/policies/tables/schema without CASCADE, revokes broker dependencies and drops the
dedicated roles.

Because the forward candidate does not modify existing `service_role` Vault grants, the
rollback does not attempt to restore them.

Once any real refresh credential exists, this structural rollback is insufficient;
provider revocation/reconnection, quarantine and backup-retention handling become a
separate mandatory procedure.

## 7. Non-authorization

This review does not authorize:

- executing either SQL file on staging;
- revoking or changing `service_role` Vault privileges;
- creating the two database roles;
- creating a password or bootstrap lease;
- creating a binding or Vault secret;
- enabling a real provider refresh exchange;
- hosted agent execution, scheduler/recurrence or report delivery;
- production prediction, prediction writes or external race-data fetching.

The next decision after this review is architectural: obtain platform-supported evidence
for narrowing the current shared Vault boundary, or use a separately isolated secret
backend/project. Until one of those paths is approved, real-secret activation remains
blocked.

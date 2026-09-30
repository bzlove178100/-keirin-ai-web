# Staging secret backend Phase A evidence

Observed: 2026-09-30 (Asia/Tokyo)
Project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`)
Status: **read-only evidence only — no migration approval**

This file records the fresh staging catalog inventory required by
`STAGING_SECRET_BACKEND_MIGRATION_REVIEW.md` Phase A. The executed statements read only
PostgreSQL catalogs/configuration and function/view definitions. They did **not** select
Vault rows, values, names, descriptions, keys, counts, application rows or provider data,
and they did not execute DDL/DML, alter grants, create roles, provision credentials,
dispatch hosted work or enable provider execution.

The SQL connection itself reported `transaction_read_only=off`; therefore this evidence
must be described as **read-only statements executed through a writable administrative
session**, not as a database-enforced read-only session. No write statement was submitted.

## Current hosted catalog

| Item | Observed value |
| --- | --- |
| PostgreSQL | `17.6` (`server_version_num=170006`) |
| Database | `postgres` |
| `supabase_vault` | `0.3.1` |
| `pgsodium` | not present in the inspected extension set |
| Vault schema owner | `supabase_admin` |
| `agent_secret_host` role | absent |
| `agent_secret_broker` role | absent |
| `agent_credential_private` schema/objects/functions | absent |
| server recovery state | primary / `pg_is_in_recovery() = false` |
| `pgrst.db_schemas` session setting | unavailable/null in this session |

The proposed agent role/schema names therefore do not currently collide with existing
staging objects.

## Vault object shapes

`vault.secrets.id` and `vault.decrypted_secrets.id` are `uuid`.

Observed hosted signatures:

- `vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) -> uuid`, `SECURITY DEFINER`, owner `supabase_admin`;
- `vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) -> void`, `SECURITY DEFINER`, owner `supabase_admin`.

The catalog also exposes internal crypto helpers. A later migration must not grant the
runtime host direct access to those helpers or to either Vault relation/view.

## Platform-role observations

`anon` and `authenticated` have no observed Vault schema usage, no SELECT on the two
inspected Vault relations and no EXECUTE on the inspected Vault functions.

`authenticator` is a LOGIN role and has SET-role memberships for `anon`, `authenticated`
and `service_role` with inheritance disabled. `service_role` has `BYPASSRLS`.

Most importantly, `service_role` currently has direct effective access that violates the
dedicated-host isolation target:

- USAGE on schema `vault`;
- SELECT and DELETE on `vault.secrets`;
- SELECT and DELETE on `vault.decrypted_secrets`;
- EXECUTE on `vault.create_secret(...)`;
- EXECUTE on `vault.update_secret(...)`;
- EXECUTE on `vault._crypto_aead_det_decrypt(...)`.

The ACL expansion confirmed these are explicit `service_role` grants in the current
catalog, not merely a conclusion inferred from role ownership.

## Dependency review performed

A metadata-only database scan found **no non-`vault` PostgreSQL function or view whose
stored definition references `vault.`**.

A repository code search on current `main` also returned no `vault.` reference.

This narrows the known dependency surface but does **not** prove that revoking
`service_role` Vault access is safe. External clients, platform-managed components,
PostgREST/API behavior, dashboards, support tooling or other service-role consumers can
exist without a stored database function/view or repository reference.

Therefore no Vault grant has been changed and no revoke statement is approved by this
evidence.

## Phase A decision

Phase A refreshed-catalog requirements are now substantially satisfied for object shape,
role membership and current effective grants. The result also confirms the existing hard
blocker rather than clearing it: the current shared Vault does not meet the design's
minimal dedicated-host isolation requirement because `service_role` can read decrypted
Vault data.

Proceeding directly to an apply-ready migration that stores agent refresh credentials in
this shared Vault would be unsafe.

Before Phase B can become apply-ready, one of these paths needs an explicit architecture
review:

1. establish, with platform-supported evidence, that the `service_role` Vault grants can
   be removed or narrowed without breaking required Supabase/platform behavior; or
2. select a separately isolated secret backend/project so the application service role
   cannot decrypt agent refresh material.

A Phase B PR may still draft fail-closed DDL for review, but it must not claim the current
staging Vault is approved for real secrets and must not auto-apply or include a real
credential.

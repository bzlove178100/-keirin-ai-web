# Secret-custody C2 review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — live schema apply blocked**

This document adapts the earlier Phase B secret-backend design to the dedicated
`keirin-ai-secret-custody` project. It does not authorize DDL, password creation, secret
provisioning or provider execution.

## 1. Architecture change from shared staging

The shared `keirin-ai-staging` Vault was rejected because its `service_role` boundary is
shared with the application project. The dedicated custody project intentionally uses a
separate blast radius instead of attempting undocumented revocation of Supabase-managed
Vault grants.

Therefore the isolated-project C2 design must **not** require `service_role` Vault grants to
be absent as an in-database precondition. The dedicated project still contains platform
roles and the fresh C1 inventory shows the normal hosted `service_role` Vault access.

The compensating boundary is external and mandatory:

- Data API disabled;
- no custody-project service/secret key distributed to the agent runtime;
- direct PostgreSQL only from the hardened host path;
- SSL enforcement enabled, with the client using verify-full;
- database/pooler ingress restricted to the approved host CIDR(s);
- project used only for credential custody.

The C2 live apply remains blocked until those management-plane properties are observed on
the actual project. Repository documentation or generic platform documentation is not
sufficient evidence.

## 2. Database preflight required before C2 apply

Immediately before any future C2 apply, the database-side preflight must still verify:

- PostgreSQL exact reviewed major/minor shape;
- `supabase_vault` exact reviewed version;
- exact hosted Vault function signatures and owners;
- `vault.secrets.id` / `vault.decrypted_secrets.id` remain UUID;
- `agent_secret_host`, `agent_secret_broker`, and `agent_credential_private` are absent;
- `auth.uid()` exists;
- no prior C2 object collides with the candidate names.

The preflight must remain catalog-only. It must not select from `vault.secrets`,
`vault.decrypted_secrets`, application tables or provider data.

`review/secret_custody_c2_db_preflight.sql` records this database-only part of the gate.
It cannot prove Data API, SSL-enforcement or network-restriction state.

## 3. Intended C2 database boundary

Once both management-plane and database preflights are clean, the future C2 migration may
create only the no-secret boundary:

- `agent_secret_host`: LOGIN, no password in migration, no superuser/role/db/replication/
  BYPASSRLS privileges;
- `agent_secret_broker`: NOLOGIN, same privilege restrictions;
- private schema `agent_credential_private`;
- `bindings` and `host_bindings` metadata tables with RLS + FORCE RLS;
- exact `read_binding(text)` and `cas_binding(text,bigint,jsonb)` SECURITY DEFINER
  functions with fixed search paths and fully qualified object names.

The runtime host receives only private-schema USAGE plus EXECUTE on the two exact entry
functions. It receives no direct metadata-table or Vault relation privilege.

The broker may receive only the minimum dependencies needed by those functions:

- private metadata SELECT/UPDATE under forced RLS;
- `auth.uid()` execution for JWT-session rejection;
- Vault schema USAGE;
- SELECT on `vault.decrypted_secrets` for mapped reads;
- DELETE on `vault.secrets` for terminal revocation;
- EXECUTE on the exact hosted `vault.update_secret(uuid,text,text,text,uuid)` function.

The runtime broker must not receive `vault.create_secret`, Vault INSERT, direct crypto-helper
EXECUTE, service-role membership, network/provider capability or API credentials.

## 4. No-secret requirement

C2 is schema qualification only. The migration must not contain or create:

- a database password;
- a provider refresh/access credential;
- a Vault secret row;
- a binding row;
- a host-to-binding row;
- a provider identifier tied to a real account;
- task payloads or production prediction state.

Initial provisioning remains an operator boundary outside C2.

## 5. Transaction and failure semantics

The future migration should execute in one bounded transaction with short lock and statement
timeouts. Any preflight mismatch must fail before object creation. It must not use CASCADE,
implicit retry, network I/O or provider calls.

The runtime CAS contract remains the already-qualified one:

- exact expected-version compare;
- row lock before mutation;
- full replacement-record validation;
- immutable provider/account/capability identity;
- same-transaction Vault mutation + metadata transition;
- no automatic replay after ambiguous writes;
- fixed outward error classifications without secret text.

## 6. Rollback qualification

C2 rollback is structural and is valid only while there are zero real/synthetic bindings and
zero Vault secrets created for this system. Before rollback it must:

- revoke host EXECUTE first;
- verify no active `agent_secret_host` session;
- verify the private metadata tables are empty;
- drop exact objects without CASCADE;
- remove only grants/roles created by C2.

Once C3 synthetic material exists, rollback requires explicit synthetic cleanup first. Once
real material exists, this structural rollback is insufficient and C4-specific provider
revocation/quarantine procedures become mandatory.

## 7. Free-plan boundary

The Free plan is retained for the cheapest current development path. That is acceptable for
C1 and review-only C2 work. It is not an availability qualification for real credential
custody because low-activity Free projects may be paused.

No paid upgrade is required for this review. Availability/cost must be resolved before C4.

## 8. Non-authorization

This review does not authorize:

- applying C2 DDL to the live custody project;
- changing Data API, SSL or network settings;
- creating a database password or bootstrap lease;
- creating a real or synthetic Vault secret;
- provider OAuth refresh or provider writes;
- hosted task execution, scheduler/recurrence or report delivery;
- production prediction, prediction writes or external race-data fetching.

The next live boundary is an authoritative management-plane configuration check/change plus
separate explicit C2 apply authorization.

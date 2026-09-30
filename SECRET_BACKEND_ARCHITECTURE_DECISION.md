# Secret backend architecture decision

Date: 2026-09-30 (Asia/Tokyo)
Status: **selected direction — no live provisioning or migration authorization**

## Decision

Do **not** store real agent refresh credentials in the shared Vault of the current
`keirin-ai-staging` project.

The preferred production/staging direction is a **separately isolated Supabase project used
only for secret custody**, with the Data API disabled and the agent runtime connecting only
through a dedicated PostgreSQL login over the already-qualified hardened direct-database
path. The existing `keirin-ai-staging` project remains the runtime/checkpoint/queue staging
project and must not become the real refresh-secret store unless a later review explicitly
reverses this decision with new platform evidence.

This document selects an architecture. It does **not** create a project, incur cost, apply
DDL, create a password, provision a secret, enable provider refresh, or enable hosted task
execution.

## Fresh evidence behind the decision

A 2026-09-30 read-only catalog check against `keirin-ai-staging`
(`omamgmyyqnawlagbemcm`) observed:

- PostgreSQL `17.6`;
- `supabase_vault` `0.3.1`;
- `vault.secrets` has RLS disabled;
- `service_role` is `NOLOGIN` and `BYPASSRLS`;
- `authenticator` can `SET ROLE service_role`;
- `service_role` has Vault schema usage;
- `service_role` has SELECT/DELETE on `vault.secrets`;
- `service_role` has SELECT/DELETE on `vault.decrypted_secrets`;
- `service_role` can execute the hosted `vault.create_secret(...)` and
  `vault.update_secret(...)` functions and the observed decrypt helper;
- `anon` and `authenticated` do not have the corresponding Vault schema usage observed in
  this inventory.

The same inspection confirmed that the hosted `vault.decrypted_secrets` view performs the
decrypt operation over `vault.secrets` and that the observed grants are explicit, not an
inference from table ownership.

No Vault row, secret value, name, description, application row or provider credential was
read during this evidence collection.

## Why the current shared Vault remains blocked

The Phase B DDL candidate can isolate the dedicated host from direct relation access, but it
cannot make the existing `service_role` unable to decrypt the same shared Vault. Therefore
placing agent refresh material there would preserve a broader decryption principal than the
agent secret-store threat model intends.

Revoking the current platform-managed `service_role` Vault grants in-place is not selected.
The current official Supabase guidance documents that grants and RLS are separate checks and
that Vault decrypted access must be protected, but the reviewed documentation does not
provide a supported hosted migration procedure proving that removing the existing Vault
`service_role` grants is dependency-free for this project.

The repository inventory also cannot prove the absence of external/dashboard/platform
consumers. A local lack of `vault.` references is therefore not sufficient evidence for a
platform-role revoke.

## Selected isolated-project boundary

A future dedicated secret-custody project must satisfy all of the following before it can
hold even a real provider refresh credential:

1. **Single purpose** — no end-user application tables, prediction data, queue state or
   general runtime workload.
2. **Data API disabled** — REST/GraphQL access is not part of the secret-store runtime
   path.
3. **No runtime service key** — the agent runtime does not receive a Supabase secret key or
   legacy `service_role` JWT for the custody project.
4. **Direct PostgreSQL only** — the hardened host uses a dedicated LOGIN role and the
   strict TLS/CA/hostname/credential-lifetime boundary already qualified in synthetic CI.
5. **Network restriction** — database/pooler ingress is allowlisted to the approved host
   path before a real credential is provisioned.
6. **SSL enforced** — plaintext PostgreSQL access is rejected.
7. **Private metadata schema** — binding metadata and exact read/CAS entrypoints remain
   outside exposed API schemas.
8. **Narrow broker** — the LOGIN role receives only EXECUTE on the exact secret-store
   functions; a NOLOGIN broker owns the minimum Vault/metadata capabilities required by
   those functions.
9. **Provisioning separated from runtime** — runtime does not receive `vault.create_secret`
   capability. Initial secret creation/reconnection remains an operator action.
10. **Bootstrap custody separated** — the database login/bootstrap credential is not stored
    in the same database it unlocks. Rotation, expiry, revocation and host injection must be
    approved and evidenced separately.
11. **No implicit failover to shared staging Vault** — loss of the custody project must
    fail closed rather than fall back to `keirin-ai-staging` Vault.
12. **No automatic activation** — creating the custody project or applying schema alone
    must not enable provider refresh, provider writes, hosted execution, recurrence,
    reporting or production prediction.

A dedicated project still contains Supabase platform roles. The isolation benefit is that
its `service_role`/authenticator boundary is not shared with the application staging
project and its service key is not distributed to the runtime path. This is a blast-radius
and credential-distribution boundary, not a claim that Supabase platform administrators or
the database owner cannot access database-resident secrets.

## Alternatives not selected

### A. Revoke `service_role` Vault grants in the current staging project

Not selected without platform-supported dependency evidence. It could reduce the principal
set, but an undocumented revoke against platform-managed roles/functions is an operational
risk and would mix application staging with secret-custody changes.

### B. Keep real secrets in current shared Vault behind private SECURITY DEFINER functions

Not selected. The dedicated host would be narrow, but the already-observed `service_role`
would still retain direct decrypted access.

### C. Encrypt a custom table in the current staging database with an application key

Not selected for now. This moves the primary problem to external key custody and adds a
custom cryptographic/key-rotation design without removing the need for a bootstrap secret.
It can be reconsidered only if the isolated-project path becomes unsuitable.

### D. Use Edge Function environment secrets as the rotating refresh-secret database

Not selected as the durable CAS backend. Environment secrets are suitable for bootstrap or
static configuration but do not match the current versioned-record/CAS/revocation contract
for per-provider rotating refresh material.

## Phase C gates

The next implementation sequence is deliberately split so that cost, DDL and real-secret
activation cannot be conflated:

### C0 — provisioning review

- determine whether a separate Supabase project is acceptable operationally and financially;
- record project ownership and environment purpose;
- define the host network/CIDR source needed for network restrictions;
- define who/what may hold the database bootstrap credential.

**No project is created until that provisioning/cost boundary is explicitly approved.**

### C1 — fresh isolated-project inventory

After a project exists, run catalog/configuration-only checks for PostgreSQL/Vault versions,
role memberships, exact function signatures, Data API state, SSL enforcement and network
restriction state. No Vault rows or application rows are read.

### C2 — no-secret schema qualification

Adapt the current reviewed Phase B candidate for the isolated project and apply only the
role/schema/function boundary. Do not create a real provider secret or binding. Verify
rollback while the private state is empty.

### C3 — synthetic credential qualification

Only after C2 is clean, provision a clearly synthetic marker through the operator path and
exercise read/CAS/revocation, restart, log-redaction and failure recovery. Remove/revoke the
synthetic material after qualification.

### C4 — real credential activation

Requires separate explicit authorization. Real provider refresh exchange, hosted execution,
provider write/generation and recurring automation remain OFF until their own gates are
approved.

## Official guidance reviewed

Current Supabase documentation reviewed for this decision includes:

- Vault / decrypted-secret access control;
- grants versus RLS and `service_role` bypass behavior;
- disabling the Data API when REST/GraphQL is not required;
- direct PostgreSQL connections for trusted servers/workers;
- database network restrictions;
- production environment separation and migration discipline.

Documentation links are intentionally kept in the Phase B review and project notes rather
than copied into executable configuration.

## Non-authorization

This decision does not authorize any of the following:

- creating a new Supabase project or branch;
- accepting any paid resource cost;
- changing `keirin-ai-staging` Vault grants;
- applying Phase B DDL to staging;
- enabling or disabling a live project's Data API;
- changing network restrictions or SSL policy;
- creating a database password/bootstrap credential;
- storing a real or synthetic Vault secret;
- provider OAuth refresh, provider writes or generation;
- hosted task execution, scheduler/recurrence or 21:00 report delivery;
- production prediction, prediction DB writes or external race-data auto-fetch.

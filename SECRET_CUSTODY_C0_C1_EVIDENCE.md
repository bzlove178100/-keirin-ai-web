# Secret-custody C0/C1 evidence

Observed: 2026-09-30 (Asia/Tokyo)
Status: **C0 provisioned at zero project cost; C1 partially qualified; no DDL or secret activation**

## C0 provisioning result

A dedicated Supabase project named `keirin-ai-secret-custody` was created in the existing
`Keirin AI` organization in `ap-northeast-1` (Tokyo). The organization is currently on the
Free plan and the project-creation cost check returned **0 per month**.

The project reported `ACTIVE_HEALTHY` immediately after creation. The organization now has
two active Free-plan projects: the existing runtime/checkpoint staging project and this
single-purpose secret-custody project.

No paid plan, compute add-on, branch, database password, provider credential, Vault secret,
binding row, migration, Edge Function or hosted task was created as part of C0.

## Cost / availability boundary

The Free plan is the cheapest current path for architecture and synthetic qualification,
but it is **not approved for real always-on credential custody**.

Current Supabase guidance states that Free-plan projects with low activity over a 7-day
period can be paused automatically, while projects under a paid plan are not subject to
that inactivity pause. Therefore:

- keep C1/C2 review work and later synthetic-only qualification on the Free project where
  practical;
- do not treat periodic keepalive traffic as an availability guarantee;
- before C4 real credential activation, require either a paid-plan availability boundary
  or another explicitly reviewed availability design;
- do not upgrade merely to continue code review or no-secret qualification.

This preserves the user's cost constraint without accepting an avoidable production outage
risk.

## C1 read-only catalog evidence

A catalog-only SQL inventory was run through the administrative connection. No Vault row,
secret value, secret name, description, application row or provider data was selected, and
no DDL/DML statement was submitted.

Observed database shape:

- PostgreSQL `17.6` (`server_version_num=170006`);
- primary database (`pg_is_in_recovery() = false`);
- `supabase_vault` `0.3.1` owned by `supabase_admin`;
- `agent_secret_host` absent;
- `agent_secret_broker` absent;
- `agent_credential_private` absent;
- `authenticator` is LOGIN and can SET ROLE `anon`, `authenticated`, and `service_role`;
- `service_role` is NOLOGIN with `BYPASSRLS`;
- `vault.secrets` and `vault.decrypted_secrets` have RLS disabled;
- `service_role` has Vault schema USAGE;
- `service_role` has SELECT/DELETE on both inspected Vault relations;
- `service_role` can execute the observed decrypt helper plus hosted
  `vault.create_secret(text,text,text,uuid)` and
  `vault.update_secret(uuid,text,text,text,uuid)` functions;
- `anon` and `authenticated` do not have the corresponding Vault schema usage or inspected
  function execution privileges.

The SQL session reported `transaction_read_only=off`; this evidence must therefore be
called **read-only statements through a writable administrative session**, not a
database-enforced read-only transaction.

The platform-role shape matching the shared staging project is expected. The dedicated
project's security value is project isolation and non-distribution of its service key, not a
claim that Supabase platform roles or the database owner cannot decrypt Vault material.

## C1 management-plane checks still open

The current connected management surface used for this run does not expose read/write
operations for all three required project settings below, so they were not guessed and were
not changed:

1. Data API disabled state;
2. Postgres SSL-enforcement state;
3. database/pooler network-restriction state and final host CIDR allowlist.

These remain hard gates before C2 live schema apply. Public documentation confirms that all
three controls exist, but documentation is not evidence of this project's current setting.

## Next boundary

Safe next work is code/review only:

1. adapt the Phase B SQL into an isolated-project C2 candidate that no longer assumes
   `service_role` privileges can be removed from a shared application project;
2. keep the candidate outside `supabase/migrations` and do not apply it;
3. define an external management-plane preflight for Data API / SSL / network restriction;
4. require fresh explicit authorization before any C2 DDL is applied to the live custody
   project.

Real or synthetic Vault secret creation, provider refresh, provider writes, hosted task
execution, scheduler/recurrence, reporting and production prediction remain disabled.

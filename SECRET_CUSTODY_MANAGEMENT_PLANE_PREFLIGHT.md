# Secret-custody management-plane preflight

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — no management-plane mutation is authorized by this file**

This runbook defines the remaining live platform gates for the dedicated secret-custody
project before C2 schema apply. It is intentionally separate from the SQL migration review.
It does not contain a project ref, access token, database password, provider credential,
Vault secret, host CIDR or other live secret material.

## Goal and cost boundary

Use the lowest-cost configuration that does not create an operational or security problem.
The current Free project is retained for review and no-secret qualification. This runbook
adds no paid add-on, compute upgrade, branch, or external service.

Do not upgrade merely to complete these checks. The separate C4 availability gate still
requires a paid-plan or equivalent availability decision before real always-on credential
custody.

## Current evidence boundary

The connected project-management surface can confirm that the dedicated project is healthy,
but it does not expose authoritative read/write tools for all three controls below. Generic
documentation is not evidence of the live project's current state.

C2 live apply remains blocked until current project-specific evidence exists for all three:

1. Data API disabled;
2. Postgres SSL enforcement enabled;
3. database/pooler network restrictions limited to the approved hardened-host CIDR set.

A security-advisor result with zero lints is useful supplementary evidence, but it does not
replace these three configuration checks.

## Least-privilege management access

If the Management API is used, use a project-scoped personal access token rather than a
classic account-wide token whenever the account supports scoped tokens.

For read-only inventory, grant only the read scopes required for:

- Data API Config;
- SSL Enforcement;
- Network Restrictions.

Add write scope only for the single control being deliberately changed, then remove or revoke
that temporary token after the change is verified. Never commit or paste the token into this
repository, CI variables, issue/PR text, logs, screenshots, or task payloads.

The repository records endpoint shapes only:

- `GET /v1/projects/{ref}/postgrest`
- `GET /v1/projects/{ref}/ssl-enforcement`
- `GET /v1/projects/{ref}/network-restrictions`

Do not infer configuration from a failed request, missing permission, or generic project
metadata. A denied management request is `unknown`, not `safe`.

## Gate A — Data API

Required state: **disabled**.

The custody project does not need browser REST or GraphQL access. With the Data API disabled,
auto-generated database HTTP endpoints are not part of the custody path.

Acceptable evidence is either:

- the current Dashboard showing **Enable Data API = off** for the custody project; or
- an authenticated, project-scoped Management API response whose current schema clearly
  reports the Data API disabled.

Do not guess a request body from an older API version. If a change is required, review the
current API schema or use the Dashboard control, perform only that single change, then read
back the state.

## Gate B — Postgres SSL enforcement

Required state: **enabled**.

The corresponding read endpoint is:

- `GET /v1/projects/{ref}/ssl-enforcement`

Supabase documents that changing SSL enforcement restarts the database. Therefore:

- do not combine the SSL change with C2 DDL;
- change it only while the custody project has no runtime dependency or stored agent secret;
- wait for the project to return healthy;
- read back the SSL-enforcement state;
- later qualify the hardened client with `sslmode=verify-full` and the pinned/approved CA
  path before any credential material is introduced.

A successful TLS connection using `require` alone is insufficient because it does not prove
CA or hostname verification.

## Gate C — database/pooler network restrictions

Required state: **applied with only the approved hardened-host egress CIDR set**.

The corresponding read endpoint is:

- `GET /v1/projects/{ref}/network-restrictions`

This gate must fail closed when the final host egress address is not known. Do not use a
world-open CIDR as a placeholder, and do not use the user's phone/home/mobile address as the
runtime allowlist.

Supabase documents that an update replaces the current allowed CIDR list. Before any future
write:

1. identify the actual hardened hosted-worker egress IPv4 and, if applicable, IPv6 CIDRs;
2. preserve every already-approved CIDR that must remain reachable;
3. verify the host can use the intended direct/pooler route with TLS `verify-full`;
4. apply the complete replacement allowlist once;
5. read back the resulting restrictions;
6. verify an approved-host connection succeeds and a non-approved route is rejected.

Do not apply network restrictions before the approved host path is stable. A guessed CIDR can
create a self-inflicted outage and is not acceptable merely to advance the checklist.

Supabase also documents that database network restrictions block direct database access from
Edge Functions. That is compatible with the current design because the custody path is the
separately hardened direct-Postgres host, not an Edge Function. If that architecture changes,
this assumption must be re-reviewed first.

## Safe change order

When authoritative management access becomes available, use this order:

1. read all three current settings without changing anything;
2. disable Data API if required, then read it back;
3. enable SSL enforcement if required, wait for health, then read it back;
4. do **not** change network restrictions until the hardened-host egress CIDR set is known and
   connection qualification is ready;
5. only after all three gates are proven may a separate explicit C2 DDL authorization be
   considered.

Each mutation is a separate reversible platform step. Do not batch unrelated settings and do
not combine them with database schema changes.

## Evidence record

For each gate record only non-secret evidence:

- observation timestamp and timezone;
- project name, not a reusable credential;
- control name;
- observed state;
- evidence method (`Dashboard` or `Management API`);
- whether a mutation occurred;
- post-change health/read-back result;
- for network restrictions, the approved host class and CIDR count, but avoid publishing
  infrastructure details in this public repository when they would expand attack surface.

Store sensitive/raw infrastructure evidence outside the public repository. The repository
should receive only a sanitized pass/fail summary.

## Hard stop conditions

Stop before C2 if any of the following is true:

- Data API state is unknown or enabled;
- SSL-enforcement state is unknown or disabled;
- hardened-host egress CIDRs are unknown or unstable;
- network restrictions are unapplied or contain an unapproved broad range;
- management access requires distributing a custody-project service key to the runtime;
- a requested change would require an unreviewed paid upgrade;
- the project does not return healthy after a platform change;
- evidence relies on a secret, a guessed setting, or an outdated API field.

No C2 schema apply, database password, Vault secret, binding row, provider refresh, provider
write, hosted task execution, scheduler/recurrence, report delivery, production prediction,
prediction DB write, or external race-data fetch is authorized by this runbook.

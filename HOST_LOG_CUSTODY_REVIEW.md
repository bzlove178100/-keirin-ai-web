# Host and PostgreSQL log custody review

Updated: 2026-09-28 (Asia/Tokyo)

## Verified base

PR #116 is merged on main at `21e9ef0355895245332ce799c9c55f0f32fbc909`.
Its post-merge regression, read-only smoke, collection UI, Pages, synthetic host/egress,
PostgreSQL/TLS recovery and PostgreSQL Bind-redaction jobs all passed. Production
prediction, prediction DB writes, automatic external race-data fetching, hosted
task/provider execution, scheduler/recurrence, provider write/generation and live report
delivery remain disabled.

The host child used for secret-bearing PostgreSQL operations redirects stdout and stderr
to `/dev/null` before credential/database work. The disposable Docker host fixture uses
log driver `none`. Those controls do not by themselves prove that the database server or
an external platform cannot log query parameters.

## PostgreSQL core session log gate

`StrictPostgresConnectionFactory` reads back the effective PostgreSQL session settings
before handing a connection to the secret backend. Core handoff requires:

- `log_statement = none`
- `log_parameter_max_length_on_error = 0`
- `log_duration = off`
- `log_min_duration_statement = -1`
- `log_min_duration_sample = -1`

The secret backend uses parameterized SQL. The gate rejects effective core paths that
would log normal statements/durations or include Bind values on an error. A mismatch uses
the existing fixed outward `postgres_host_factory_unavailable` classification; raw
server/driver error text is not exposed or retried.

## Extension parameter-log gate

The same preflight now checks custom settings with missing-setting semantics so a server
without those extensions remains compatible:

- If `auto_explain` settings are absent, the extension path is treated as inactive.
- If `auto_explain` is active, either `auto_explain.log_min_duration = -1` must disable
  plan logging or `auto_explain.log_parameter_max_length = 0` must suppress Bind values.
- If pgAudit is active, `pgaudit.log_parameter` must be `off`.
- A partially visible or malformed `auto_explain` setting pair fails closed.

This closes extension-specific parameter logging while allowing non-secret query/plan
metadata where Bind values are explicitly suppressed. Unit tests cover absent, disabled,
parameter-suppressed, malformed and unsafe states. The disposable PostgreSQL 17 contract
also applies unsafe auto_explain/pgAudit role settings and requires rejection, then proves
an active auto_explain configuration with parameter length zero is accepted.

A read-only hosted metadata review was performed without reading log messages or secret
rows. It confirmed that the hosted PostgreSQL log stream is active and that extension
logging settings are material to this deployment. The current hosted profile does not yet
meet every strict handoff condition, so the real secret backend remains intentionally
unbound; no hosted configuration was changed by the review.

## Observed server-log Bind redaction

The synthetic test starts a disposable PostgreSQL 17 TLS server and creates only synthetic
roles/passwords. Through the strict factory it submits an extended-protocol parameterized
query whose Bind value is a fixed synthetic secret marker and deliberately causes a
division-by-zero error. The observer reads `docker logs` into memory without printing the
payload. The fixed `division by zero` text must be present as a positive control proving the
server error-log channel was observed, while the Bind marker must be absent.

No real provider, database row, account credential, token, refresh secret or prediction
data is used by this evidence.

## Scope and remaining gates

This qualifies the effective PostgreSQL session policy, auto_explain/pgAudit parameter-log
settings and the disposable PostgreSQL stderr/Docker capture path used by CI. It does
**not** qualify cloud-provider control-plane logs, Docker daemon/systemd journals,
kernel/audit logs, APM/tracing, WAL/archive/backup contents, host storage erasure,
retention, log-access authorization or end-to-end hosted log-drain custody. It also does
not make the preflight immutable against a privileged database/host administrator changing
policy after handoff; that remains part of the deployment administration boundary.

Before any real secret-backend migration or provider refresh integration, the remaining
operational review must cover platform/provider log custody, privileged host/Docker/database
administration, retention/access/restore behavior and deployment-specific daemon/host faults.
No activation switch changes in this code/CI-only slice.

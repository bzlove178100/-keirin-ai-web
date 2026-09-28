# Host and PostgreSQL log custody review

Updated: 2026-09-29 (Asia/Tokyo)

## Verified base

PR #117 is merged on main at `8551bd11df542b7cd8a1e5252c8bef07324b43af`.
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
- If `auto_explain` is loaded, `auto_explain.log_min_duration = -1` must disable
  plan logging. Suppressing only the Bind parameter list is insufficient: a custom
  verbose plan can contain the bound value as a constant.
- If pgAudit is active, `pgaudit.log_parameter` must be `off`.
- A partially visible or malformed `auto_explain` setting pair fails closed.

PR #117 checked custom GUC readback but did not load the actual extension in CI.
The current correction rejects every enabled auto_explain plan logger, including
`log_parameter_max_length=0`, and validates the parameter-length range. It preserves
absent-extension compatibility and pgAudit's parameter-off gate.

The new synthetic CI case explicitly LOADs auto_explain in an isolated admin session,
forces custom plans with verbose logging and a suppressed parameter list, and requires
a fixed synthetic marker to appear in the observed plan log. That positive control
cannot use real credentials. It then preloads the actual module in the dedicated login,
requires enabled plan logging to block strict handoff, disables plan logging and checks
that a different bound marker is returned by a successful query but absent from logs.
Missing module, missing positive-control evidence or leaked protected marker fails CI.
This does not constitute behavioral qualification of the pgAudit module.

Local factory tests (16) and persistence-redaction tests (3) pass. Docker is absent
locally; actual loaded-extension evidence requires successful final-head PostgreSQL CI.

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

## Reference checked for the correction (2026-09-29)

[PostgreSQL 17 auto_explain](https://www.postgresql.org/docs/17/auto-explain.html)
documents the distinct plan-duration, parameter-list and verbose-plan controls.
The synthetic loaded-module test, rather than setting readback alone, is the required
evidence for the custom-plan constant exposure and protected-session behavior.

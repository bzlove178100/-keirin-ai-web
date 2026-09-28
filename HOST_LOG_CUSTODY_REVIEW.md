# Host and PostgreSQL log custody review

Updated: 2026-09-28 (Asia/Tokyo)

## Verified base

PR #115 is merged on main at `52447966bafac70869c98db71220b56ecf70ff70`.
Its post-merge regression, collection UI, Pages, synthetic host/egress and PostgreSQL/TLS
recovery jobs all passed. Production prediction, prediction DB writes, automatic external
race-data fetching, hosted task/provider execution, scheduler/recurrence, provider
write/generation and live report delivery remain disabled.

The host child used for secret-bearing PostgreSQL operations already redirects stdout and
stderr to `/dev/null` before credential/database work. The disposable Docker host fixture
uses log driver `none`. Those controls do not by themselves prove that the database server
or an external platform cannot log query parameters.

## PostgreSQL session log gate

`StrictPostgresConnectionFactory` now reads back the effective PostgreSQL session settings
before handing a connection to the secret backend. Handoff requires all of the following:

- `log_statement = none`
- `log_parameter_max_length_on_error = 0`
- `log_duration = off`
- `log_min_duration_statement = -1`
- `log_min_duration_sample = -1`

The secret backend uses parameterized SQL. The gate therefore rejects the effective paths
that would log normal statements/durations or include Bind values on an error. A mismatch
uses the existing fixed outward `postgres_host_factory_unavailable` classification; raw
server/driver error text is not exposed or retried.

Unit tests mutate every added preflight field and require rollback/close with no handoff.
The Docker/PostgreSQL qualification separately applies each unsafe role override to a
fresh TLS session and requires the factory to fail closed, then resets the override and
requires a healthy connection again.

## Observed server-log Bind redaction

The synthetic test starts a disposable PostgreSQL 17 TLS server and creates only synthetic
roles/passwords. Through the strict factory it submits an extended-protocol parameterized
query whose Bind value is a fixed synthetic secret marker and deliberately causes a
division-by-zero error. The observer reads `docker logs` into memory without printing the
payload. The fixed `division by zero` text must be present as a positive control proving the
server error-log channel was observed, while the Bind marker must be absent.

No real provider, database, account, endpoint, token, refresh secret or prediction data is
used by this evidence.

## Scope and remaining gates

This slice qualifies the effective PostgreSQL session policy and the disposable PostgreSQL
stderr/Docker capture path used by CI. It does **not** qualify cloud-provider control-plane
logs, Docker daemon/systemd journals, kernel/audit logs, APM/tracing, extension logs such as
`pgaudit` or `auto_explain`, WAL/archive/backup contents, host storage erasure, retention,
log-access authorization, or Supabase/platform log custody. It also does not make the
preflight immutable against a privileged database/host administrator changing policy after
handoff; that remains part of the deployment administration boundary.

Before any real secret-backend migration or provider refresh integration, the remaining
operational review must cover platform/provider log custody, privileged host/Docker/database
administration, retention/access/restore behavior and deployment-specific daemon/host faults.
No activation switch changes in this code/CI-only slice.

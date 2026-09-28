# Host and PostgreSQL log custody review

Updated: 2026-09-29 (Asia/Tokyo)

**Synthetic/CI evidence only. No real secret backend, hosted execution or production log policy is activated by this review.**

## Verified base

Current verified main is PR #121 merge `b8321d556476eeb04bc8d557f52a17a8d2f7ed5a`.
Its post-merge regression, read-only smoke, collection UI, PostgreSQL/host contract and
Pages workflows passed. Production prediction, prediction DB writes, automatic external
race-data fetching, hosted task/provider execution, scheduler/recurrence, provider
write/generation and live report delivery remain disabled.

## Application and container boundary

The secret-bearing child redirects stdout/stderr to `/dev/null` before credential/database
work. Synthetic hardened-host fixtures use Docker log driver `none`; a separate `json-file`
positive control proves the observer can retrieve known non-secret markers while the
`none` profile must not expose them through Docker logs.

This does not prove absence from daemon/systemd journals, kernel audit facilities,
tracing/APM, platform telemetry or other privileged host channels.

## PostgreSQL core session log gate

`StrictPostgresConnectionFactory` reads effective PostgreSQL session settings before
handing a connection to the secret backend. Core handoff requires:

- `log_statement = none`;
- `log_parameter_max_length_on_error = 0`;
- `log_duration = off`;
- `log_min_duration_statement = -1`;
- `log_min_duration_sample = -1`.

The backend uses parameterized SQL. Unsafe or malformed effective policy fails closed with
the fixed outward `postgres_host_factory_unavailable` classification and no automatic
retry.

The synthetic PostgreSQL 17 log-custody contract observes the real disposable server log
channel in memory. A deliberate division-by-zero error is required as a positive control,
while a fixed synthetic Bind marker supplied through the strict factory must be absent.
No real token, account credential, provider secret, prediction row or private race data is
used.

## `auto_explain` gate

PR #118 corrected the earlier custom-GUC-only evidence. Parameter-list suppression alone
is insufficient because a verbose custom plan can contain a bound value as a constant.
The strict handoff therefore requires `auto_explain` plan logging itself to be disabled.

The synthetic CI case LOADs the actual `auto_explain` module, forces a verbose custom plan
with parameter-list logging suppressed and requires a fixed positive marker to appear in
the observed plan log. It then proves that a dedicated login with enabled plan logging is
rejected, disables plan logging, performs a protected query and requires its different
synthetic marker to be absent from logs. Missing module, missing positive-control evidence
or a protected marker leak fails the contract.

## pgAudit status

The preflight checks `pgaudit.log_parameter=off` when the setting is present. This is a
configuration gate only. The repository still has **no behavioral qualification of the
actual pgAudit module** comparable to the loaded `auto_explain` test.

Do not install an unpinned or moving pgAudit package merely to turn this item green. A
future behavioral test should use a pinned/reproducible module source or image, prove the
log channel with a non-secret positive control and prove a protected synthetic parameter
is absent under the exact policy expected for deployment.

## Network/TLS/daemon evidence that narrows logging risk

Later host work changes the scope of this review:

- PR #114 pins the approved synthetic host image digest and fixed launcher;
- PR #115 qualifies the dedicated internal network, exact membership and synthetic
  permitted-destination/blocked-egress controls;
- PR #119 composes PostgreSQL TLS inside the hardened client/container and exact internal
  network, with wrong-hostname and wrong-CA negative controls. The client receives no DB
  credential in that composition test;
- PR #120 performs an actual Docker daemon restart on the GitHub-hosted Linux/systemd
  profile with `live-restore=false` and `restart=no`, requiring the synthetic process tree
  not to resurrect and exact fresh-interpreter reconciliation to leave an unrelated
  sentinel untouched.

These controls reduce unreviewed transport/runtime paths in synthetic CI. They do not
qualify privileged platform log custody or production administrator behavior.

## Hosted metadata observation

A prior bounded read-only hosted metadata review, performed without reading log messages or
secret rows, established that the hosted PostgreSQL log stream is active and that extension
logging settings are material to the intended deployment. The observed hosted profile did
not satisfy every strict secret-handoff condition, so the real secret backend remained
unbound. This review does not change hosted configuration.

## Remaining custody gates

Before any real secret-backend migration or provider refresh integration, the deployment
review still must cover:

- cloud/platform control-plane and database log destinations;
- Docker daemon/systemd journal, kernel/audit and host telemetry/APM channels;
- who can read, export, restore or alter those logs and settings;
- retention, deletion, backup/archive and restore behavior;
- WAL/archive/backup contents and database administrator access;
- production tracing/frame-local/crash-dump policy;
- privileged host/root/kernel/ptrace/operator custody;
- actual pgAudit behavior if pgAudit is part of the selected deployment;
- policy-change behavior after handoff and the administrative boundary that can mutate it.

Synthetic absence of a marker in one observed channel is not evidence that every external
platform channel is safe. Platform/provider evidence must come from the selected deployment
and its documented/configured controls, not from a simulated CI substitute.

## Activation boundary

No activation switch changes in this review. Real secret migration, provider refresh,
hosted execution, long-lived host, scheduler/recurrence, production prediction, prediction
DB writes, external race-data fetching and live report delivery remain separately gated.

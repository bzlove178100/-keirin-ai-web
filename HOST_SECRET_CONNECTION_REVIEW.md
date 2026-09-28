# Host secret connection review

Updated: 2026-09-29 (Asia/Tokyo)

**Design and synthetic/CI evidence only. No production secret factory, real endpoint or bootstrap credential is bound.**

## Verified base

Current verified main is PR #121 merge `b8321d556476eeb04bc8d557f52a17a8d2f7ed5a`.
Its post-merge regression, read-only smoke, collection UI, PostgreSQL/host contract and
Pages workflows passed. Production prediction, prediction DB writes, automatic external
race-data fetching, hosted task/provider execution, scheduler/recurrence, provider
write/generation and live report delivery remain disabled.

## Connection and secret-backend boundary

The synthetic PostgreSQL 17 path now qualifies the following code-only controls:

- bounded connection/statement/lock timeouts and process deadline enforcement;
- fixed outward error classification, no automatic write replay and authoritative read-back
  for ambiguous writes;
- direct dedicated logins with identity/database/read-write/primary-state checks;
- `sslmode=verify-full`, reviewed CA material and rejection of wrong hostname, wrong CA,
  expired certificate and plaintext transport;
- strict ambient configuration rejection for libpq/OpenSSL overrides, pass/service files
  and unsupported client-certificate fallback;
- reviewed CA SHA-256 plus sealed Linux memory snapshot and no-follow file acquisition;
- immutable bootstrap lease metadata with login/database/version/expiry/revocation fencing;
- child loader/Python environment guards, core-dump suppression, `dumpable=0`,
  `no_new_privs=1`, private umask and Linux parent-death SIGKILL;
- cgroup-v2 memory/swap/PID/CPU limits, non-root execution, dropped capabilities,
  read-only root/code and bounded ephemeral `/tmp`;
- PID-namespace descendant cleanup and external-controller exact reconciliation;
- approved immutable Python image digest and fixed launcher;
- dedicated internal network with exact membership and synthetic allowed-destination /
  blocked-egress controls;
- PostgreSQL TLS handshake from the hardened client composition, with hostname and CA
  negative controls;
- Docker daemon restart recovery on the exercised GitHub-hosted Linux/systemd profile
  with `live-restore=false` and `restart=no`.

These controls are cumulative synthetic evidence. They do not select or authorize a live
endpoint, credential source, secret migration or hosted execution path.

## Hardened-host TLS composition

PR #119 composes a disposable PostgreSQL TLS server with the hardened client/container
and exact internal network. The client is held behind a release marker until exact network
membership has been verified. A valid reviewed synthetic CA and expected DNS identity
must complete the TLS handshake; a wrong hostname or wrong CA must fail.

The hardened client receives no database credential in this test. Therefore this evidence
qualifies transport composition under the tested host/network restrictions, but does **not**
by itself qualify authenticated secret reads/CAS inside that exact container composition.
The separate strict-factory PostgreSQL tests cover authentication and secret operations.
Do not collapse those two evidence sets into a claim of production end-to-end readiness.

## Daemon restart and reconciliation

PR #120 adds an actual Docker daemon restart to the synthetic host contract on the
GitHub-hosted Linux/systemd runner profile. The test requires `live-restore=false`,
`restart=no`, an exact immutable target identity and an unrelated sentinel. It records
pidfd, `/proc` and cgroup evidence, restarts Docker through systemd, requires the target
process tree not to resurrect, then uses a fresh interpreter to remove only the exact
target. A second reconciliation must be absent/no-op, prior process/cgroup evidence must
be gone and the sentinel must survive.

This is narrower than host-failure qualification. It does not prove recovery after machine
reboot, power loss, kernel panic, hostile root/daemon control or a production supervisor.

## Proposed live profile and remaining evidence

A later live factory must remain separately reviewed and operator-configured.

| Boundary | Required behavior | Current status |
| --- | --- | --- |
| Destination | One operator-approved primary endpoint/database/port; no task-provided DSN, host lists or automatic failover | Real destination remains unconfigured |
| Transport | `sslmode=verify-full`, reviewed immutable trust material, approved hostname, bounded connection settings | Synthetic transport and hardened-host composition qualified; real endpoint/pin lifecycle unconfigured |
| Database identity | Dedicated non-admin login; exact database/session identity; primary/read-write checks; no role switching | Synthetic direct-login/session checks qualified; actual hosted grants remain a deployment gate |
| Database privileges | Narrow read/CAS functions only; no direct secret-table access | Synthetic SQL/ACL contract exists; real Vault/database grants unqualified |
| Bootstrap credential | Resolve only inside the child from an approved host facility; no admin/service-role secret, task input, repo file or command line | Real host facility, ownership, rotation and revocation unconfigured |
| Trust/config custody | Controlled launcher, immutable image/trust files, clean environment, protected operator provisioning | Synthetic image/launcher/CA controls qualified; real host/root/kernel/operator custody unqualified |
| Time/retries | One fresh bounded connection; no pool/background retry; no automatic replay after ambiguous writes | Synthetic deadline/lost-ack/recovery evidence qualified |
| Error/logging | Fixed outward codes; no secret-bearing connection string, SQL parameter, row or raw exception in persisted logs | Synthetic application/Docker/PostgreSQL evidence exists; platform/host custody still open |
| Recovery | Authoritative read-back after ambiguous writes; exact cleanup/reconciliation; no blind replay | Synthetic DB/process/controller/daemon evidence exists; real provider/Vault and host reboot/power-loss recovery unqualified |

## Remaining operational gates

Before any real secret-backend migration or provider refresh integration, evidence is still
required for:

- real bootstrap credential facility, ownership, rotation and revocation;
- actual Vault encryption/key lifecycle and intended hosted grants;
- platform/host log access, retention, restore and telemetry custody;
- production root/kernel/ptrace/swap and administrator boundaries;
- host reboot/power-loss and production supervisor/reconciler behavior;
- authenticated database secret operations inside the final production-equivalent hardened
  network/container composition;
- deployment-specific DNS/address lifecycle and trust/pin distribution.

A real-backend migration must be a separate reviewed change. Do not combine migration,
credential activation and hosted task execution in one step.

## References

Implementation/tests are based on the documented behavior of PostgreSQL 17 libpq TLS and
connection parameters, Docker resource/network/logging controls and Linux process/cgroup
primitives already cited in repository history. Those references establish component
semantics; they do not establish the security of an untested deployment.

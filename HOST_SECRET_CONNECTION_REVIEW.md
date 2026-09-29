# Host secret connection review

Updated: 2026-09-29 (Asia/Tokyo)

**Design and synthetic/CI evidence only. No production secret factory, real endpoint or bootstrap credential is bound.**

## Verified base

Current verified main is PR #125 merge `1293aea494a840cba92cac364e24ade9f818dee7`.
Its post-merge `keirin-ai regression`, collection UI, PostgreSQL/host contract and Pages workflows all passed. Production prediction, prediction DB writes, automatic external race-data fetching, hosted task/provider execution, scheduler/recurrence, provider write/generation and live report delivery remain disabled.

## Connection and secret-backend boundary

The synthetic PostgreSQL 17 path qualifies these code-only controls:

- bounded connection/statement/lock timeouts and process deadline enforcement;
- fixed outward error classification, no automatic write replay and authoritative read-back for ambiguous writes;
- direct dedicated logins with identity/database/read-write/primary-state checks;
- verify-full TLS, reviewed CA material and wrong hostname/CA, expired-certificate and plaintext rejection;
- strict ambient libpq/OpenSSL configuration rejection and unsupported client-certificate fallback rejection;
- reviewed CA SHA-256 plus sealed Linux memory trust snapshot;
- immutable bootstrap lease login/database/version/expiry/revocation fencing;
- child loader/Python guards, core-dump suppression, `dumpable=0`, `no_new_privs=1`, private umask and Linux parent-death SIGKILL;
- cgroup-v2 memory/swap/PID/CPU limits, non-root execution, dropped capabilities, read-only root/code and bounded ephemeral `/tmp`;
- PID-namespace cleanup and external-controller exact reconciliation;
- approved immutable Python image digest and fixed launcher;
- dedicated internal network with exact membership and synthetic permitted-destination/blocked-egress evidence;
- PostgreSQL TLS from the hardened client composition with hostname/CA negative controls;
- Docker-daemon restart recovery on the exercised GitHub-hosted Linux/systemd profile;
- actual pgAudit parameter-redaction behavior in the disposable qualified profile;
- authenticated TLS/SCRAM-SHA-256 private secret read/CAS inside the exact hardened client/network composition.

These controls are cumulative synthetic evidence. They do not select or authorize a live endpoint, credential source, secret migration or hosted execution path.

## Authenticated hardened-host composition

PR #125 extends the PR #119 transport-only composition without adding a real credential or live endpoint.

The disposable client uses the already approved immutable Python image/launcher and the same hardened controls: 128 MiB memory with no additional swap, PID/CPU limits, read-only root, dropped capabilities, `no-new-privileges`, non-root identity, Docker log driver `none`, restart policy `no`, core limit zero, bounded tmpfs and read-only test/trust mounts.

The client and disposable PostgreSQL server are the only members of the dedicated internal network. Exact membership is verified before either the synthetic bootstrap password is handed to the client or the client release marker permits its first database socket.

The fixed synthetic password is passed only over Docker exec stdin into the client's tmpfs after that preflight; it is not placed in the container environment. A stdlib PostgreSQL v3 client performs TLS 1.2+ hostname/CA verification and SCRAM-SHA-256 authentication as `secret_test_host_a`.

After authentication the probe verifies session/database/read-write/TLS identity, reads only its mapped private binding, proves the other binding is denied, performs a versioned CAS, confirms durable read-back, proves stale CAS returns the fixed conflict without replay, and verifies the unrelated binding is unchanged. The composed application-name session must be gone afterward.

This closes the earlier authenticated transport/private-SQL composition gap. It does **not** prove that `StrictPostgresConnectionFactory` plus `ProcessDeadlinePostgresSecretBackend` itself is executing inside that exact immutable client image. Those application components remain separately qualified by the existing process/TLS/PostgreSQL tests. A later composition must preserve the immutable-image/launcher trust boundary; ambient host site-packages or unpinned runtime dependency installation are not acceptable substitutes.

## Daemon restart and reconciliation

PR #120 adds an actual Docker daemon restart to the synthetic host contract on the GitHub-hosted Linux/systemd runner profile. The test requires `live-restore=false`, `restart=no`, an exact immutable target identity and an unrelated sentinel. The target process tree must not resurrect, fresh-interpreter reconciliation removes only the exact target, a second reconciliation is absent/no-op, prior PID/cgroup evidence disappears and the sentinel survives.

This remains narrower than host-failure qualification. It does not prove machine reboot, power loss, kernel panic, hostile root/daemon control or a production supervisor.

## Proposed live profile and remaining evidence

A later live factory must remain separately reviewed and operator-configured.

| Boundary | Required behavior | Current status |
| --- | --- | --- |
| Destination | One operator-approved primary endpoint/database/port; no task-provided DSN, host lists or automatic failover | Real destination remains unconfigured |
| Transport | verify-full TLS, immutable reviewed trust, approved hostname, bounded settings | Synthetic hardened transport/auth composition qualified; real endpoint/pin lifecycle unconfigured |
| Database identity | Dedicated non-admin login; exact database/session identity; primary/read-write checks; no role switching | Synthetic direct-login and composed SCRAM session checks qualified; actual hosted grants remain a deployment gate |
| Database privileges | Narrow read/CAS functions only; no direct secret-table access | Synthetic SQL/ACL and composed mapped-read/CAS evidence qualified; real Vault/database grants unqualified |
| Bootstrap credential | Resolve only inside protected host execution from an approved facility; no admin/service-role secret, task input, repo file or command line | Synthetic post-membership tmpfs handoff is qualified only as fixture evidence; real host facility, ownership, rotation and revocation unconfigured |
| Trust/config custody | Controlled launcher, immutable image/trust files, clean environment, protected provisioning | Synthetic image/launcher/CA controls qualified; real host/root/kernel/operator custody unqualified |
| Time/retries | One fresh bounded connection; no pool/background retry; no automatic replay after ambiguous writes | Synthetic deadline/lost-ack/recovery evidence qualified |
| Error/logging | Fixed outward codes; no secret-bearing connection string, SQL parameter, row or raw exception in persisted logs | Synthetic application/Docker/PostgreSQL/pgAudit evidence exists; platform/host custody still open |
| Recovery | Authoritative read-back after ambiguous writes; exact cleanup/reconciliation; no blind replay | Synthetic DB/process/controller/daemon evidence exists; real provider/Vault and host reboot/power-loss recovery unqualified |
| Application composition | Actual strict factory/process backend inside the final hardened immutable client boundary | Component tests and raw authenticated composition both pass separately; co-resident application-stack composition remains open |

## Remaining operational gates

Before any real secret-backend migration or provider refresh integration, evidence is still required for:

- real bootstrap credential facility, ownership, rotation and revocation;
- actual Vault encryption/key lifecycle and intended hosted grants;
- platform/host log access, retention, restore and telemetry custody;
- production root/kernel/ptrace/swap and administrator boundaries;
- host reboot/power-loss and production supervisor/reconciler behavior;
- actual strict-factory/process-backend execution inside an equivalently hardened immutable container composition;
- deployment-specific DNS/address lifecycle and trust/pin distribution.

A real-backend migration must be a separate reviewed change. Do not combine migration, credential activation and hosted task execution in one step.

## References

Implementation/tests are based on the documented behavior of PostgreSQL 17 TLS/SCRAM and connection parameters, Docker resource/network/logging controls and Linux process/cgroup primitives already cited in repository history. Those references establish component semantics; they do not establish the security of an untested deployment.

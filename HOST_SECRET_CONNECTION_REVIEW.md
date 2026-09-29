# Host secret connection review

Updated: 2026-09-29 (Asia/Tokyo)

**Design and synthetic/CI evidence only. No production secret factory, real endpoint or bootstrap credential is bound.**

## Verified base

Current verified functional main through PR #131 is `1c6d3e84632fa451629738d0720ad4f029599a23`.
Its post-merge `keirin-ai regression`, collection UI, PostgreSQL/host contract and Pages workflows all passed. The PostgreSQL/host run includes the co-resident application stack, fail-closed rejection cases, row-lock/process-deadline case, raw authenticated composition, TLS/restart recovery, log-policy and pgAudit checks. Production prediction, prediction DB writes, automatic external race-data fetching, hosted task/provider execution, scheduler/recurrence, provider write/generation and live report delivery remain disabled.

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
- authenticated TLS/SCRAM-SHA-256 private secret read/CAS inside the exact hardened client/network composition;
- the actual application strict-factory/process-backend/durable-store chain executing co-resident inside the hardened immutable client;
- fail-closed co-resident application behavior for invalid trust/name and stale/revoked/expired bootstrap leases;
- bounded co-resident row-lock failure with fixed ambiguous-write classification, no replay and verified unchanged durable state after cleanup.

These controls are cumulative synthetic evidence. They do not select or authorize a live endpoint, credential source, secret migration or hosted execution path.

## Authenticated hardened-host composition

PR #125 extended the PR #119 transport-only composition without adding a real credential or live endpoint.

The disposable client uses the approved immutable Python image/launcher and hardened controls: 128 MiB memory with no additional swap, PID/CPU limits, read-only root, dropped capabilities, `no-new-privileges`, non-root identity, Docker log driver `none`, restart policy `no`, core limit zero, bounded tmpfs and read-only test/trust mounts.

The client and disposable PostgreSQL server are the only members of the dedicated internal network. Exact membership is verified before either the synthetic bootstrap password is handed to the client or the client release marker permits its first database socket.

The fixed synthetic password is passed only over Docker exec stdin into the client's tmpfs after that preflight; it is not placed in the container environment. A stdlib PostgreSQL v3 client performs TLS 1.2+ hostname/CA verification and SCRAM-SHA-256 authentication as `secret_test_host_a`.

After authentication the raw probe verifies session/database/read-write/TLS identity, reads only its mapped private binding, proves the other binding is denied, performs a versioned CAS, confirms durable read-back, proves stale CAS returns the fixed conflict without replay, and verifies the unrelated binding is unchanged. The composed application-name session must be gone afterward.

## Actual application-stack hardened composition

PR #127 closed the prior co-residency gap while preserving the immutable-image/launcher boundary.

Inside the same hardened client profile, the test runs the actual application classes:

`StrictPostgresConnectionFactory -> ProcessDeadlinePostgresSecretBackend -> PostgresSecretBackend -> DurableVersionedSecretStore`.

The private SQL fixture is remapped to the real opaque binding key produced by `DurableVersionedSecretStore.key_for(...)`. Synthetic bootstrap password/version material is handed into tmpfs only after exact two-member network verification. The strict factory then performs its existing reviewed-CA snapshot/sealing, bootstrap lease/current-version checks, TLS/SCRAM connection, identity/privilege/session/log-policy preflight and handoff before backend operations are allowed.

The initial co-resident test proves durable read, versioned CAS, fresh read-back, fixed stale-version conflict without replay, preservation of the unrelated binding and process/database-session cleanup.

PR #129 extends that exact co-resident boundary with negative cases. Bad CA pin/trust, stale bootstrap version, revoked lease, expired lease and wrong TLS hostname all fail closed through the application stack and leave the synthetic durable state unchanged. These are composition claims, not merely repetitions of the earlier component tests.

PR #131 extends the same boundary with a real row-lock fault. The fixture first locks the target binding row. The application then attempts CAS with an outer 1.5-second process deadline while its server lock/statement limits are deliberately longer. The operation returns only the fixed ambiguous-write classification; there is no automatic replay. After the lock holder and killed child are cleaned up, the target record remains at its original version/secret, the unrelated binding remains unchanged, application and fixture database sessions reach zero, and the exclusive network returns to server-only membership.

During PR #131 development, the test-only stdlib PostgreSQL shim initially exposed a modeling defect: it declared `autocommit=False` but did not open an explicit server transaction before statements, allowing a statement to autocommit independently of the application `connection.commit()` call. The fixture was corrected to issue `BEGIN` before the first statement and explicitly model `COMMIT`/`ROLLBACK` state. The final row-lock evidence passed only after this correction. Therefore the current no-commit/no-replay result is based on transaction-faithful synthetic behavior rather than the earlier fixture artifact.

To avoid either bind-mounting ambient host site-packages or installing an unpinned dependency into the approved immutable Python client, PR #127-#131 use a **test-only stdlib PostgreSQL protocol/DB-API shim** for this composition. The shim implements only the surface required by the real application classes. Existing pinned psycopg/libpq process/TLS/recovery tests remain separate evidence for the intended production driver. The shim is not a production driver, and these composition tests do not by themselves prove final deployment packaging/provenance of psycopg/libpq and native dependencies.

## Daemon restart and reconciliation

PR #120 adds an actual Docker daemon restart to the synthetic host contract on the GitHub-hosted Linux/systemd runner profile. The test requires `live-restore=false`, `restart=no`, an exact immutable target identity and an unrelated sentinel. The target process tree must not resurrect, fresh-interpreter reconciliation removes only the exact target, a second reconciliation is absent/no-op, prior PID/cgroup evidence disappears and the sentinel survives.

This remains narrower than host-failure qualification. It does not prove machine reboot, power loss, kernel panic, hostile root/daemon control or a production supervisor.

## Proposed live profile and remaining evidence

A later live factory must remain separately reviewed and operator-configured.

| Boundary | Required behavior | Current status |
| --- | --- | --- |
| Destination | One operator-approved primary endpoint/database/port; no task-provided DSN, host lists or automatic failover | Real destination remains unconfigured |
| Transport | verify-full TLS, immutable reviewed trust, approved hostname, bounded settings | Synthetic hardened transport/auth/application composition and wrong-name/trust rejection qualified; real endpoint/pin lifecycle unconfigured |
| Database identity | Dedicated non-admin login; exact database/session identity; primary/read-write checks; no role switching | Synthetic direct-login and co-resident strict-factory checks qualified; actual hosted grants remain a deployment gate |
| Database privileges | Narrow read/CAS functions only; no direct secret-table access | Synthetic SQL/ACL and co-resident opaque-key read/CAS evidence qualified; real Vault/database grants unqualified |
| Bootstrap credential | Resolve only inside protected host execution from an approved facility; no admin/service-role secret, task input, repo file or command line | Synthetic post-membership tmpfs handoff plus stale/revoked/expired lease rejection are fixture evidence only; real host facility, ownership, rotation and revocation unconfigured |
| Trust/config custody | Controlled launcher, immutable image/trust files, clean environment, protected provisioning | Synthetic image/launcher/CA controls qualified; real host/root/kernel/operator custody unqualified |
| Time/retries | One fresh bounded connection; no pool/background retry; no automatic replay after ambiguous writes | Co-resident row-lock/process-deadline composition now qualifies the bounded ambiguous-write/no-replay case; real deployment timing remains unqualified |
| Error/logging | Fixed outward codes; no secret-bearing connection string, SQL parameter, row or raw exception in persisted logs | Synthetic application/Docker/PostgreSQL/pgAudit evidence exists; platform/host custody still open |
| Recovery | Authoritative read-back after ambiguous writes; exact cleanup/reconciliation; no blind replay | Synthetic DB/process/controller/daemon and co-resident lock/deadline evidence exists; real provider/Vault and host reboot/power-loss recovery unqualified |
| Application composition | Actual strict factory/process backend/durable store inside hardened immutable client | Synthetic positive, rejection and bounded-lock compositions qualified through PR #131; final production-driver packaging/provenance remains separate |

## Remaining operational gates

Before any real secret-backend migration or provider refresh integration, evidence is still required for:

- real bootstrap credential facility, ownership, rotation and revocation;
- actual Vault encryption/key lifecycle and intended hosted grants;
- platform/host log access, retention, restore and telemetry custody;
- production root/kernel/ptrace/swap and administrator boundaries;
- host reboot/power-loss and production supervisor/reconciler behavior;
- final deployment packaging/provenance for the intended psycopg/libpq stack and native dependencies;
- deployment-specific DNS/address lifecycle and trust/pin distribution.

The planned synthetic co-resident application slice is complete through success, fail-closed lease/trust/name rejection and bounded row-lock/process-deadline behavior. Additional CI should require a distinct identified gap, not merely duplicate evidence.

The next safe step is a **review-only** staging migration package describing intended schema/grants, bootstrap-secret ownership/rotation/revocation, trust/pin lifecycle, rollback and observation. A real-backend migration must remain a separate explicitly approved change. Do not combine migration, credential activation and hosted task execution in one step.

## References

Implementation/tests are based on the documented behavior of PostgreSQL 17 TLS/SCRAM and connection parameters, Docker resource/network/logging controls and Linux process/cgroup primitives already cited in repository history. Those references establish component semantics; they do not establish the security of an untested deployment.

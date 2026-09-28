# Host secret connection review

Reviewed 2026-09-27. **Design/CI evidence only; no production factory or credential is bound.**

## Current evidence

`PostgresSecretBackend` supplies connection, statement and lock limits. The opt-in
`ProcessDeadlinePostgresSecretBackend` adds child-process deadline/termination and
fixed result handling. Neither selects a live endpoint or owns a bootstrap credential.

The disposable PostgreSQL 17 contract now exercises that process wrapper with direct
`secret_test_host_a` / `secret_test_host_b` logins. The test creates synthetic passwords
only on temporary roles and checks session/current identity, database and read/write
state in each fresh child connection. No SET ROLE or session-identity switching is used
by this new factory. Existing earlier identity-switching tests remain separate.

The factory fixes loopback host/address, port 5432, the disposable database, login,
application name, and read/write requirement. Its `sslmode=disable` is intentionally
limited to this isolated plaintext fixture and is **not an approved live profile**.
Passing this test does not demonstrate TLS, Vault encryption or deployment readiness.

The next slice adds a separate Docker TLS fixture in `tests/run_secret_tls_contract.py`.
It generates a temporary CA, valid/expired server certificates and a distinct wrong CA;
performs process-wrapped TLS read/CAS; and rejects wrong hostname/CA, expired certificates
and a reachable plaintext server. Private keys stay in disposable files and are removed
with the fixture. PR #104 passed the TLS suite and all required PR/main workflows.

`PostgresHostProfile` fixes transport settings and rejects malformed/multiple targets,
DSN-like input and known privileged login names without I/O. It is a parameter policy,
not an endpoint allowlist, privilege audit or live factory. It accepts operator-approved
configuration only; callers must not derive it from task inputs or override its output.

The current slice adds `StrictPostgresConnectionFactory` for use inside a trusted
top-level deadline-child factory. It accepts an injected driver and password source;
construction performs no I/O. Calls reject noncanonical timeouts and ambient libpq/TLS
configuration before accessing the source, require a nonempty bounded password and
disable client-certificate/passfile fallback and require SCRAM-SHA-256 authentication.
Session preflight checks actual identity,
database, TLS, primary/read-write status, privilege flags, absence of role memberships
and server timeout values, then commits the preflight SELECT transaction before
returning the connection. Every failure closes/rejects with fixed outward errors.

Ambient rejection is intentionally strict: any `PG*` variable, `OPENSSL_CONF`,
`OPENSSL_MODULES`, `SSL_CERT_FILE` or `SSL_CERT_DIR`, or default `.pgpass`,
`.pg_service.conf` / `.postgresql` in either home location blocks the factory. It does
not mutate the environment or inspect file contents. This is not proof against an
already-compromised interpreter/driver, OS loader configuration or TOCTOU changes.
Deployment must provide a controlled host environment and protected trust/config files.

The current slice adds a reviewed CA hash and a sealed Linux memory snapshot. Protected
directory FDs and no-follow opens reject symlinks, mutable permissions, unexpected owner,
multiple links and nonregular/oversized files. The content hash, metadata stability and
kernel write/grow/shrink seals are required; unsupported kernels fail closed. Only the
sealed descriptor path reaches libpq. The configured hash must come from approved
provisioning, never from the candidate file during each connection. The trusted host/root
account, kernel and profile/pin distribution remain security assumptions.

Bootstrap sources now provide an immutable redacted lease plus a version-current check.
The factory checks exact login/database, version, expiration and current/revoked state
before connecting and after preflight; it rejects stale/expired leases without replay.
The callback owns authoritative source state. It must return exactly True only for the
currently authorized version, perform no hidden retries and expose no secret in errors.
It is checked at handoff, not continuously: closing or revoking existing DB sessions and
distributed rotation orchestration remain outside this contract. No real source is bound.

## Proposed live profile and evidence still required

These are engineering requirements for a later, separately reviewed host factory.
They do not select a real endpoint or change any deployed configuration.

| Boundary | Required behavior | Evidence/status |
| --- | --- | --- |
| Destination | One operator-approved primary endpoint/database/port; no task-provided DSN, host lists or automatic failover | Real destination unconfigured; deny unknown/multiple targets in the eventual factory |
| Transport | Explicit `sslmode=verify-full`, reviewed `sslrootcert` trust file and `gssencmode=disable` when TLS is mandatory | Trusted certificate must succeed; wrong CA/name, expired certificate and plaintext server must fail in synthetic TLS tests |
| Endpoint identity | Use the approved hostname for certificate checks; if a numeric `hostaddr` is fixed, retain that hostname and review DNS/address lifecycle | `hostaddr` alone is not server identity proof; no real address pinned |
| Primary state | `target_session_attrs=read-write`, then verify database, `session_user`, `current_user`, non-recovery and read/write state before secret operations | Direct-login CI checks these; read/write status alone does not prove the operator-approved server identity |
| Database privileges | Dedicated non-admin login, narrow read/CAS functions, exact allowed bindings, no role switching or direct secret-table access | Synthetic SQL/ACL and direct-login process tests; actual Vault grants remain a blocker |
| Bootstrap credential | Resolve only inside child from an approved host facility; no administrator or service-role secret, task input, repository file or command-line credential | Host facility and rotation remain unconfigured |
| Ambient configuration | Review/neutralize `PG*`, service/pass files, home-directory certificates, proxy settings and driver defaults; explicit security fields must not be overridden | A raw `psycopg.connect(**kwargs)` wrapper is not a qualified live factory |
| Time/retries | Pass adapter timeout kwargs unchanged, one fresh connection, no pool/background reconnect/write retry; keep process deadline and supervisor limits | Unit/process/loopback blackhole evidence; deployment-specific network and supervisor qualification still open |
| Error/logging | Fixed outward codes; no connection string, SQL parameters, rows, exception text or frame locals in logs/traces/core dumps | Synthetic error/stdout/stderr tests; database, platform and host logging review still open |
| Recovery | Child termination never proves server rollback; perform bounded authoritative read-back and preserve ambiguous state until evidence resolves it | Actual commit-with-lost-ack and lock-kill CI scenarios; real provider/Vault recovery remains untested |

The future factory must connect with bounded settings, verify identity before exposing
the connection, close on rejection, and return an idle transaction-capable connection.
Factories and their imports are trusted host code, must not create descendant processes,
and must not read bootstrap secrets at import time. Parent/child memory policies and
an external supervisor remain required even with process isolation.

## Next executable validation

PR #107 verified synthetic TLS process/server restart, crash-after-commit, lease/TLS
rejection, DB pause and terminal record revocation.

The next code-only slice rejects LD_/DYLD_ variables and selected Python import/debug
overrides before spawn, without reading/logging values or silently sanitizing them.
After redirecting stdout/stderr, each deadline child sets and verifies RLIMIT_CORE=(0,0),
Linux dumpable=0 and no_new_privs=1, and sets umask 077 before decoding secret IPC or
calling the factory. Failure exits the child: reads stay unavailable, writes ambiguous,
without retry. Parent resource limits/privileges are unchanged; unsupported OS/syscall
behavior fails closed.

This does not secure an already modified interpreter/loader, eliminate environment
check/spawn races or protect imports executed before the spawned child target. Imports
must remain trusted and side-effect-free. A trusted launcher must supply a fixed clean
environment before interpreter startup. no_new_privs does not remove existing privileges;
trusted code can change dumpable again. Root/kernel/ptrace capabilities, swap, telemetry,
database/platform logs and parent memory remain outside these safeguards.

The next slice arms Linux PR_SET_PDEATHSIG=SIGKILL in the child before request
decode and factory work, verifies PR_GET_PDEATHSIG, and checks getppid against the
PID captured by the spawning parent before and after registration. A missing parent
or failed syscall/readback exits without a reply. Synthetic subprocess tests kill
the parent with TERM and KILL while the factory ignores TERM; a disposable subreaper
waits for the child and verifies its SIGKILL exit. This covers termination of the
direct child after registration, not arbitrary descendants or secure memory erasure.

Linux ties the signal to the creating thread, not the lifetime of every parent
thread. Factories must not fork, change effective/filesystem IDs, or reset this
control. Startup/imports before registration remain trusted and require external
supervision. Child termination cannot determine whether a database write committed;
recovery still requires authoritative read-back and must not automatically replay.

## Disposable resource-limit qualification

`AGENT_EPHEMERAL_HOST_TEST=1 python tests/run_host_limits_contract.py` requires
Docker with cgroup v2 and creates a separate disposable container per probe. It
checks Docker configuration before startup and actual cgroup files before stress:
128 MiB memory, no swap, 24 tasks and 50,000/100,000 microseconds of CPU bandwidth.
These are fixture values, not sizing recommendations or a production host profile.
CPU throttling counters must increase, a bounded synthetic allocation child must
receive SIGKILL with an OOM-kill counter increment, and bounded fork attempts must
hit EAGAIN with the pids-controller counter increment. Children are reaped and
containers are removed even after timeout; cleanup failure fails the contract.

Existing OS and parent-death guard tests also run inside these limits. Containers
use a non-root identity, dropped capabilities, no-new-privileges, read-only code/root,
an ephemeral bounded /tmp, no network and Docker log driver `none`. Network/logging
settings are fixture precautions only; no egress or platform-log qualification is
claimed by this resource test. The runner resolves the Python image tag once to a
local immutable image ID and records that ID. Image provenance/approved digest and
actual deployment qualification are still open; the test tag can change between runs.

The local environment lacks Docker, so only fixture gate/cleanup tests and syntax
checks can run there. The dedicated CI job must pass actual enforcement and existing
guard compatibility before merge. Missing controllers or readback mismatches fail;
there is no skip/fallback to unbounded execution or RLIMIT_NPROC (which is UID-wide
and not a substitute for cgroup task limits).

## PID-namespace supervisor fault qualification

The same gated Docker runner also starts a synthetic PID-1 supervisor, a child and
a grandchild in a separate session/process group. All three ignore TERM. After
readiness and host-side topology/cgroup checks, separate cases inject immediate
`os._exit(23)` in the supervisor and Docker stop with a one-second TERM grace period
(expected forced-kill exit 137). No application cleanup runs on the crash path.

Before injecting the fault, the observer opens stable pidfds for all three host PIDs
and records their /proc start times. Success requires every pidfd to report exit,
every original /proc identity to disappear (readability alone can mean a zombie),
and the cgroup to be absent or explicitly unpopulated with no listed processes.
Container removal and absence verification run on failure as well as success; all
observer FDs are closed. Missing or incomplete evidence fails the contract. This
verifies namespace-wide teardown, including a descendant outside the original
process group; it does not authorize production factories to spawn descendants.

The outer Docker daemon/CI observer remains alive in those tests. Daemon/host
failure is NOT qualified. Resource/cgroup and Linux PID namespace behavior in this fixture
does not prove a deployment's supervisor configuration or durable DB outcomes.
Ambiguous writes still require read-back and must not be blindly replayed.

## Synthetic external-controller restart reconciliation

The next fixture uses a separate external controller process, not the container's
PID 1. A private temporary run-intent file is written before creation. Each resource
has a unique synthetic label/name and a fixed image ID. Cases kill the controller
with SIGKILL immediately after creation but before its ID receipt is saved, and
after the supervisor/child/detached-grandchild tree is running. The observer must
confirm that controller death actually leaves the created/running resource behind.

A fresh Python interpreter reads the intent, discovers only its exact run label,
rejects multiple candidates, and checks full ID (when receipted), name, image and
container restrictions. Removal targets the full immutable ID; absence is read back.
A second fresh interpreter must report absent without another removal. The running
case additionally requires the prior stable pidfd/proc/cgroup cleanup evidence.
An unrelated synthetic sentinel must survive target reconciliation. Unit tests reject
wrong receipts, labels, names, images, privileges, duplicate candidates and invalid
intent schemas; failed/uncertain removal is not blindly retried inside reconciliation.

This is test-only code. The Docker daemon and outer CI observer stay alive; host
power loss, daemon failure, hostile label/intent manipulation, concurrent controllers
and a deployed always-on reconciler remain unqualified. Temporary JSON receipts
contain synthetic resource identities only, no credentials or database state. No
real action is automatically resumed or replayed, and no activation switch changes.

Next qualify controlled launcher/image
integrity, permitted-destination egress, and platform/database log custody. No real
host is declared ready by these tests. Full TLS/database composition under deployment
limits is not covered by this network-disabled fixture.
Keep real endpoints, credentials, staging migration, provider refresh and hosted execution
out of this code/CI-only sequence.

## Official references checked

OS references checked 2026-09-28:
- [Linux PID namespace init termination](https://www.man7.org/linux/man-pages/man7/pid_namespaces.7.html)
- [Linux pidfd exit observation](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)
- [Linux cgroup v2 resource controllers](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
- [Linux parent-death signal](https://www.man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html)
- [Linux parent process ID](https://www.man7.org/linux/man-pages/man2/getppid.2.html)
- [Python resource limits](https://docs.python.org/3.12/library/resource.html)
- [Linux dumpable control](https://www.man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html)
- [Linux no_new_privs](https://www.man7.org/linux/man-pages/man2/PR_SET_NO_NEW_PRIVS.2const.html)

- [PostgreSQL 17 connection parameters](https://www.postgresql.org/docs/17/libpq-connect.html):
  `host` / `hostaddr`, per-host connection timeout, `sslmode`, `gssencmode` and
  `target_session_attrs` semantics. `verify-full` checks CA trust and hostname;
  GSS encryption can otherwise take precedence over TLS. Unix sockets ignore `sslmode`.
- [PostgreSQL 17 SSL support](https://www.postgresql.org/docs/17/libpq-ssl.html):
  certificate chain/hostname verification and root certificate handling.

These references establish client behavior, not the security of an untested deployment.

The factory also follows the documented [libpq environment defaults](https://www.postgresql.org/docs/17/libpq-envars.html)
and `sslcertmode=disable` behavior in the connection-parameter reference. The client
certificate option requires compatible libpq; CI uses the pinned psycopg binary driver.

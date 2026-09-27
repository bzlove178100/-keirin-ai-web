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
with the fixture. CI evidence must be checked before calling this slice verified.

`PostgresHostProfile` fixes transport settings and rejects malformed/multiple targets,
DSN-like input and known privileged login names without I/O. It is a parameter policy,
not an endpoint allowlist, privilege audit or live factory. It accepts operator-approved
configuration only; callers must not derive it from task inputs or override its output.

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

After the ephemeral TLS fixture passes, implement an unbound factory that enforces
the profile, rejects unsafe ambient configuration and validates actual session identity.
Qualify secret-source custody, trust-file ownership and host supervisor limits separately.
Keep real endpoints, credentials, staging migration, provider refresh and hosted execution
out of this code/CI-only sequence.

## Official references checked

- [PostgreSQL 17 connection parameters](https://www.postgresql.org/docs/17/libpq-connect.html):
  `host` / `hostaddr`, per-host connection timeout, `sslmode`, `gssencmode` and
  `target_session_attrs` semantics. `verify-full` checks CA trust and hostname;
  GSS encryption can otherwise take precedence over TLS. Unix sockets ignore `sslmode`.
- [PostgreSQL 17 SSL support](https://www.postgresql.org/docs/17/libpq-ssl.html):
  certificate chain/hostname verification and root certificate handling.

These references establish client behavior, not the security of an untested deployment.

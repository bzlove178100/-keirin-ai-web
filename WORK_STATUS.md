# Work status

Updated: 2026-09-29 (Asia/Tokyo).

This file is the current resumption snapshot. Detailed historical implementation notes remain available in Git history and merged PRs; they are intentionally not duplicated here.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless the user explicitly authorizes a new, specific boundary:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**;
- no real provider/OAuth refresh exchange is connected;
- no real durable secret backend is activated.

Agent-only checkpoint/activity persistence and queue coordination in staging were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

Current verified functional baseline through PR #131:

`1c6d3e84632fa451629738d0720ad4f029599a23`

PR #131 (`Qualify hardened application row-lock deadline`) merged after all exact-head PR workflows passed. Its post-merge main workflows also passed.

Documentation synchronization PR #132 then merged to main as:

`0c6fa49b289122178221a35b8e768e49c0109a1f`

Its post-merge main checks also passed, including:

- `agent runtime read-only smoke`;
- `keirin-ai regression`;
- `collection progress UI regression`;
- `agent checkpoint PostgreSQL contract`;
- Pages build/deployment.

The PostgreSQL contract includes the co-resident actual application stack, fail-closed lease/trust/hostname rejection cases, the real row-lock/process-deadline case, host limits, raw authenticated composition, TLS/restart recovery, PostgreSQL log-policy checks and pgAudit parameter-redaction checks.

Do not treat a later functional main SHA as verified until its required workflows are checked again.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Last bounded read-only staging verification remains from the authentication-boundary work; no new live run was started in PR #101-#132 work:

- single-active trusted-run guard: present;
- fresh trusted tasks observed then `queued` / `running`: 0;
- `race_predictions`: 0 rows;
- `agent-runtime-dev`: v6 / ACTIVE / `verify_jwt=true`;
- `agent-exact-claim-dev`: v1 / ACTIVE / `verify_jwt=true`.

A previous one-run authorization is consumed. A future workflow dispatch or any new hosted execution requires new explicit live-run authorization. Code merge, persistence authorization, workflow presence or old approvals are not execution authorization.

## Current autonomous-agent capability

Implemented and merged foundations include:

- durable owner-scoped checkpoint/activity state;
- crash-safe queue lease/fencing, attempt limits and expired-lease reconciliation;
- immutable TaskSpec identity, exact-task claim and one-active-fresh-trusted-run guard;
- fail-closed hosted worker coordination with runtime execution gate kept OFF;
- credential-isolated hosted transport and SHA-pinned GitHub/CI observation;
- hard run deadlines and proposal-only recovery decisions;
- manual one-shot host workflow, not automatically dispatched;
- static and refresh-capable credential-provider abstractions;
- version/CAS refresh-secret ownership, rotation and ambiguous-state recovery semantics;
- durable secret-backend adapter contract;
- credential-gated provider-action boundary;
- persistence-safe fixed action/verifier errors and static redaction audit;
- host-only ephemeral diagnostic metadata sink;
- offline full credential-stack composition without live provider binding.

The project is still **not** an always-on self-contained autonomous agent. Scheduler/recurrence, provider write/generation, real secret custody, real refresh exchange, hosted task execution and report delivery remain disabled/unconfigured.

## Secret backend / PostgreSQL boundary

PR #100 established synthetic PostgreSQL 17 full refresh-record/CAS behavior.

PR #101-#106 added and qualified the bounded host adapter stack:

- injected PostgreSQL connection creation with fixed error classification and no automatic retry;
- process deadline/TERM/KILL/quarantine semantics for hangs and ambiguous writes;
- real PostgreSQL integration and lost-ack/read-back recovery;
- explicit verify-full TLS profile and wrong CA/name/expired/plaintext rejection;
- strict connection factory with ambient PG/OpenSSL override rejection and direct-login/privilege/session checks;
- reviewed CA SHA-256, sealed Linux memfd trust snapshot and bootstrap credential version/expiry/revocation fencing.

No live endpoint, live bootstrap secret, Vault migration or production factory is bound.

A **review-only** staging migration package is now prepared in
`STAGING_SECRET_BACKEND_MIGRATION_REVIEW.md` with a catalog-only preflight query in
`ops/staging_secret_backend_preflight.sql`. Neither file is a migration and neither applies
or authorizes database changes. No file for this package has been added under
`supabase/migrations`.

## Host/process hardening and recovery qualification

Merged synthetic/code-only qualification now covers:

- PR #107: child loader/Python environment guards, core-dump suppression, Linux dumpable/no_new_privs and private umask;
- PR #108: Linux parent-death SIGKILL guard before secret acquisition;
- PR #109-#110: disposable cgroup-v2 resource enforcement for memory, swap, PID and CPU limits;
- PR #111: PID-namespace supervisor crash/forced-stop descendant cleanup;
- PR #112: external-controller SIGKILL and fresh-interpreter exact reconciliation;
- PR #113: no-network evidence and Docker log-driver positive/negative controls;
- PR #114: approved immutable Python image digest plus fixed launcher;
- PR #115: dedicated internal Docker network with exact membership and synthetic permitted-destination/blocked-egress evidence;
- PR #116: effective PostgreSQL core log-policy checks and observed Bind-marker absence;
- PR #117-#118: auto_explain/pgAudit preflight and loaded auto_explain behavioral correction;
- PR #119: PostgreSQL TLS handshake composed inside the hardened client/container and exact internal network, with valid CA/name positive control and wrong-name/wrong-CA rejection;
- PR #120: Docker daemon restart on the exercised GitHub-hosted Linux/systemd profile with exact reconciliation and no target resurrection;
- PR #123: actual pgAudit parameter-redaction behavior in a disposable PostgreSQL 17.11/bookworm profile;
- PR #125: authenticated PostgreSQL secret operations inside the exact hardened client/container and internal-network composition, including mapped private read/CAS, cross-binding denial, stale-CAS conflict and durable read-back;
- PR #127: the actual application secret stack runs co-resident inside the approved immutable hardened client: `StrictPostgresConnectionFactory` + `ProcessDeadlinePostgresSecretBackend` + `PostgresSecretBackend` + `DurableVersionedSecretStore` execute against the disposable private SQL contract with the real opaque binding key;
- PR #129: the same co-resident application composition fails closed for bad CA pin/trust, stale/revoked/expired bootstrap leases and wrong hostname without mutating the durable synthetic record;
- PR #131: a real PostgreSQL row lock blocks the application CAS while the outer process deadline is shorter than server lock/statement limits. The outward result is the fixed ambiguous-write classification, there is no automatic replay, the target and unrelated records remain unchanged after cleanup, and application/fixture database sessions are reaped.

During PR #131 qualification, the test-only stdlib PostgreSQL shim exposed a fixture mismatch: it advertised `autocommit=False` without opening an explicit server transaction. The shim was corrected to issue `BEGIN` before the first statement and to model `COMMIT`/`ROLLBACK` state explicitly. The row-lock test only passed after this correction, so the current synthetic no-commit evidence is based on transaction-faithful fixture behavior rather than an autocommit artifact.

PR #127-#131 use a **test-only stdlib PostgreSQL protocol shim** inside the immutable Python image so the tests do not bind-mount ambient host site-packages or install an unpinned runtime dependency. Existing psycopg/libpq process/TLS tests remain separate evidence for intended production-driver behavior. The shim is not a production driver and does not prove final deployment packaging of psycopg/libpq/native dependencies.

PR #120 remains limited to the exercised GitHub-hosted Linux/systemd Docker-daemon profile. It does not prove machine reboot, power-loss, kernel-panic or hostile-root recovery.

PR #123 remains limited to its disposable pgAudit profile. It does not prove the selected hosted deployment uses the same module/version/configuration or that external platform logs have acceptable custody.

## Logging / credential-custody status

Current synthetic evidence includes fixed outward errors, no exception payload persistence, child stdout/stderr suppression, Docker `none` log-driver tests, PostgreSQL core Bind-redaction checks, loaded `auto_explain` protection and actual pgAudit parameter-redaction behavior.

Still unqualified or deployment-specific:

- platform/host log custody, access, export, backup and retention;
- selected deployment pgAudit version/configuration and the administrative boundary that can mutate it;
- tracing/frame-local/host telemetry policy in a real deployment;
- real bootstrap credential facility, ownership, rotation and revocation;
- real Vault encryption/key lifecycle and current staging Vault grant remediation;
- production/root/kernel/ptrace/swap and operator custody;
- host reboot/power-loss recovery and production deployment supervisor behavior;
- final deployment packaging/provenance of the intended PostgreSQL driver and its native dependencies;
- deployment DNS/address lifecycle and trust/pin distribution.

Synthetic evidence must not be described as end-to-end platform or production qualification.

## Keirin prospective evaluation

Owner-only dry-run remains the validation path. Unknown odds are not invented. Probabilities remain uncalibrated for monetary EV / production promotion.

The recorded first eligible prospective sample is 2026-09-24 Ito Onsen 1R (7 riders, all 210 model probabilities, 72 confirmed pre-race trifecta odds, valid chronology). The last recorded state had one distinct eligible prediction time; the evaluator's technical minimum is five distinct times and boundary purging can require more. Five is not evidence of accuracy or profitability.

## Next work / next boundary

The planned synthetic co-resident application-stack slice is complete through fail-closed lease/trust/hostname rejection and bounded row-lock/process-deadline behavior. More CI cases should be added only for a distinct, identified gap rather than to accumulate duplicate evidence.

The review-only staging migration package is prepared. It defines intended schema/role/grant boundaries, bootstrap-credential ownership/rotation/revocation requirements, trust/pin lifecycle, rollback, observation and hard blockers. Its preflight SQL is catalog/configuration-only and deliberately avoids Vault/application rows.

Preferred order:

1. keep exact-head CI and post-merge main verification as merge gates;
2. merge the review-only package only if its CI is clean; this merge itself authorizes no live staging action;
3. before drafting actual migration DDL, obtain a **fresh read-only staging catalog inventory** for PostgreSQL/Vault versions, exact Vault function signatures/owners, role memberships and effective privileges. Treat this as a separate live staging evidence step rather than silently executing it during code review;
4. use that refreshed evidence to draft a separate timestamped migration PR with exact DDL and rollback, still without a password or real secret and still without automatic apply;
5. keep platform/host log custody and production administrator/root/kernel claims open until the selected deployment can provide real evidence; do not simulate them in CI;
6. keep host reboot/power-loss and production supervisor behavior open until an environment can produce representative evidence;
7. only after the operational gates and migration review are explicitly approved, perform a separate staging migration. Do not combine migration, credential activation and hosted task execution in one change;
8. keep live hosted execution, long-lived host, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery disabled until separately authorized.

No race screenshots or owner credential resend is needed for the current code-only/review-only work.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

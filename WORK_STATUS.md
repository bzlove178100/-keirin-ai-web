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

Current verified main through PR #125:

`1293aea494a840cba92cac364e24ade9f818dee7`

PR #125 (`Qualify authenticated secret operations in hardened host composition`) merged after all exact-head PR workflows passed. Its four post-merge main workflows also passed:

- `keirin-ai regression`;
- `collection progress UI regression`;
- `agent checkpoint PostgreSQL contract`;
- Pages build/deployment.

Do not treat a later main SHA as verified until its required workflows are checked again.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Last bounded read-only staging verification remains from the authentication-boundary work; no new live run was started in PR #101-#125 work:

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
- PR #125: authenticated PostgreSQL secret operations inside the exact hardened client/container and internal-network composition. Exact network membership is verified before synthetic bootstrap handoff or the first client socket. A stdlib TLS/SCRAM-SHA-256 client authenticates as the dedicated synthetic login, performs mapped private `read_binding` and CAS, proves cross-binding denial, verifies stale-CAS conflict without replay, and confirms durable read-back while the unrelated binding remains unchanged.

PR #125 closes the previous transport/auth/private-SQL composition gap, but it intentionally does **not** claim that the application `StrictPostgresConnectionFactory` + `ProcessDeadlinePostgresSecretBackend` stack itself runs inside that exact immutable client image. Those application components remain separately qualified by their existing PostgreSQL/TLS/process tests.

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
- actual application strict-factory/process-backend execution inside the final hardened immutable container composition;
- deployment DNS/address lifecycle and trust/pin distribution.

Synthetic evidence must not be described as end-to-end platform or production qualification.

## Keirin prospective evaluation

Owner-only dry-run remains the validation path. Unknown odds are not invented. Probabilities remain uncalibrated for monetary EV / production promotion.

The recorded first eligible prospective sample is 2026-09-24 Ito Onsen 1R (7 riders, all 210 model probabilities, 72 confirmed pre-race trifecta odds, valid chronology). The last recorded state had one distinct eligible prediction time; the evaluator's technical minimum is five distinct times and boundary purging can require more. Five is not evidence of accuracy or profitability.

## Next work / next boundary

Code-only work may continue without another live-run authorization.

Preferred order:

1. keep exact-head CI and post-merge main verification as merge gates;
2. if it can be done without weakening the immutable-image/launcher boundary, qualify the real application strict-factory/process-backend composition inside an equivalently hardened disposable client; do not solve this by bind-mounting ambient host site-packages or by unpinned runtime installs;
3. keep platform/host log custody and production administrator/root/kernel claims open until the selected deployment can provide real evidence; do not simulate them in CI;
4. keep host reboot/power-loss and production supervisor behavior open until an environment can produce representative evidence;
5. after documented operational gates are closed, prepare a **separate** staging migration/review for a real backend. Do not combine migration, credentials and task execution in one change;
6. keep live hosted execution, long-lived host, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery disabled until separately authorized.

No race screenshots or owner credential resend is needed for the current code-only work.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.

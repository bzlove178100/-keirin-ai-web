# Work status

Updated: 2026-09-30 (Asia/Tokyo).

This file is the current resumption snapshot. Detailed historical implementation notes remain in Git history and merged PRs.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless a new, specific boundary is explicitly authorized:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**;
- no real provider/OAuth refresh exchange is connected;
- no real provider credential or refresh secret is stored in the new custody project;
- no live secret-store schema has been applied to the new custody project.

Agent-only checkpoint/activity persistence and queue coordination in `keirin-ai-staging` were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

PR #136 (`Select isolated project boundary for real agent secret custody`) merged to `main` as:

`25fe90185bd0fabe29890d7d3cde459068350b24`

Its post-merge workflows passed, including `keirin-ai regression`, `collection progress UI regression`, `agent checkpoint PostgreSQL contract`, host-limits qualification and Pages build/deployment.

The PostgreSQL contract still covers the co-resident actual application stack, fail-closed lease/trust/hostname rejection, real row-lock/process-deadline behavior, hardened host limits, TLS/restart recovery, log-policy checks and pgAudit parameter-redaction checks.

## Runtime staging project

Existing runtime/checkpoint staging remains:

- project: `keirin-ai-staging`;
- region: `ap-northeast-1`;
- provider/runtime execution gates remain OFF;
- prediction DB writes and external race-data fetching remain OFF.

Do not repurpose this shared application staging Vault for real agent refresh-secret custody. The 2026-09-30 Phase A inventory confirmed `service_role` can directly access decrypted Vault data in that project.

## Secret-custody architecture

PR #136 selected a separate Supabase project as the future secret-custody boundary rather than modifying the shared application staging Vault.

The required final boundary remains:

- single-purpose secret-custody project;
- Data API disabled;
- runtime receives no custody-project service key;
- hardened direct PostgreSQL only;
- SSL enforced and client uses verify-full trust/hostname checks;
- database/pooler ingress restricted to the approved host path;
- dedicated LOGIN host plus NOLOGIN broker;
- private metadata schema and exact read/CAS functions;
- provisioning capability separated from runtime;
- bootstrap credential custody external to the database;
- no fallback to shared staging Vault.

## C0 — dedicated project provisioning

User approved the cheapest path provided it does not create an operational problem.

A dedicated project named `keirin-ai-secret-custody` was created in the existing `Keirin AI` organization in `ap-northeast-1` (Tokyo).

Current organization plan: **Free**.

The project-creation cost check returned **0 per month** and the project reported `ACTIVE_HEALTHY` after creation. This uses the second active Free-project slot; the organization currently has the runtime staging project plus the custody project.

No branch, paid add-on, password, secret, binding, DDL, Edge Function or hosted work was created during C0.

## Free-plan availability gate

Free is acceptable for current architecture work and synthetic/no-secret qualification, but it is **not approved for real always-on credential custody**.

Supabase currently documents that low-activity Free projects may be paused after a 7-day activity window, whereas projects on paid plans are not subject to that inactivity pause. Therefore a paid-plan availability decision or an explicitly reviewed alternative must be resolved before C4 real credential activation.

Do not generate artificial keepalive traffic and call that an availability guarantee. Do not upgrade merely for code review or no-secret testing.

## C1 — fresh isolated-project inventory

Read-only catalog statements were executed against `keirin-ai-secret-custody`. No Vault row/value/name/description, application row or provider credential was read; no DDL/DML statement was submitted.

Observed:

- PostgreSQL `17.6` (`server_version_num=170006`), primary;
- `supabase_vault` `0.3.1`, owner `supabase_admin`;
- `agent_secret_host`, `agent_secret_broker`, `agent_credential_private`: absent;
- `authenticator` is LOGIN and can SET ROLE `anon`, `authenticated`, `service_role`;
- `service_role` is NOLOGIN with `BYPASSRLS`;
- `vault.secrets` and `vault.decrypted_secrets` have RLS disabled;
- `service_role` has Vault schema USAGE, SELECT/DELETE on the inspected Vault relations, and EXECUTE on the observed create/update/decrypt functions;
- `anon` and `authenticated` do not have the corresponding inspected Vault access;
- SQL session reported `transaction_read_only=off`, so evidence is read-only statements through a writable administrative session, not a database-enforced read-only transaction.

The platform-role shape is expected. Project isolation is the security boundary; it is not a claim that Supabase platform administrators or the database owner cannot decrypt database-resident Vault material.

## C1 management-plane gates still open

The connected management surface used in this run does not expose authoritative read/write controls for all required settings below, so none were guessed or changed:

1. Data API disabled state;
2. Postgres SSL-enforcement state;
3. database/pooler network restrictions and final approved host CIDR.

These remain hard gates before any C2 live schema apply. Documentation proving the controls exist is not evidence that this project's settings currently satisfy them.

See `SECRET_CUSTODY_C0_C1_EVIDENCE.md` for the current C0/C1 record.

## Next work / next boundary

Safe next work is code/review only:

1. adapt the Phase B candidate into an isolated-project C2 review artifact;
2. keep it outside `supabase/migrations` and do not apply it;
3. define a management-plane preflight for Data API, SSL enforcement and network restriction;
4. require fresh explicit authorization before any C2 DDL is applied to the live custody project;
5. after C2 and rollback qualification, use only clearly synthetic credential material for C3;
6. require a separate availability/cost decision plus explicit authorization before C4 real credential activation.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

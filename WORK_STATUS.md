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
- no real provider credential or refresh secret is stored in the custody project;
- no live secret-store schema has been applied to the custody project;
- no paid hardened host has been provisioned.

Agent-only checkpoint/activity persistence and queue coordination in `keirin-ai-staging` were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

PR #140 (`Select lowest-cost hardened host candidate`) merged to `main` as:

`8dfbc0cd1459fc4fe4717460e14691508aaa681c`

Its exact-head CI passed. Its post-merge main workflows also completed without a failure, including the regression, collection UI, read-only runtime, PostgreSQL/host contract and Pages paths.

The PostgreSQL contract continues to cover the co-resident application stack, fail-closed lease/trust/hostname rejection, real row-lock/process-deadline behavior, hardened host limits, TLS/restart recovery, log-policy checks and pgAudit parameter-redaction checks.

## Runtime staging project

Existing runtime/checkpoint staging remains:

- project: `keirin-ai-staging`;
- region: `ap-northeast-1`;
- provider/runtime execution gates remain OFF;
- prediction DB writes and external race-data fetching remain OFF.

Do not repurpose this shared application staging Vault for real agent refresh-secret custody. The 2026-09-30 Phase A inventory confirmed `service_role` can directly access decrypted Vault data in that project.

## Secret-custody project

A dedicated project named `keirin-ai-secret-custody` exists in `ap-northeast-1` (Tokyo).

Current organization plan: **Free**. Project-creation cost check returned **0 per month** and the project is currently `ACTIVE_HEALTHY`.

The live security-advisor check returned zero lints. This is supplementary evidence only; it does not prove the management-plane gates below.

No paid add-on, branch, database password, Vault secret, binding row, provider credential, Edge Function or hosted worker was created for the custody path.

## C0 / C1 complete boundary

`SECRET_CUSTODY_C0_C1_EVIDENCE.md` records the dedicated-project provisioning and catalog-only inventory.

Observed database shape includes:

- PostgreSQL 17.6 family, primary;
- `supabase_vault` 0.3.1;
- proposed private roles/schema absent;
- hosted `service_role` retains normal Vault privileges inside the dedicated project;
- no secret row/value/name/description or provider credential was read;
- no DDL/DML was submitted during C1.

Project isolation, not revocation of Supabase-managed platform privileges, is the selected blast-radius boundary.

## C2 review artifacts complete

PR #138 added the isolated-project C2 review artifacts, intentionally outside `supabase/migrations`:

- `SECRET_CUSTODY_C2_REVIEW.md`;
- `review/secret_custody_c2_candidate.sql`;
- `review/secret_custody_c2_rollback.sql`;
- regression guards for the no-secret/no-live-apply boundary.

The candidate keeps the dedicated LOGIN host / NOLOGIN broker split, private metadata schema, forced RLS, exact read/CAS functions, no runtime `vault.create_secret` capability, no password, no binding row and no secret provisioning.

**C2 has not been applied to Supabase.**

## Management-plane preflight

PR #139 added `SECRET_CUSTODY_MANAGEMENT_PLANE_PREFLIGHT.md`. It defines three project-specific hard gates:

1. Data API disabled;
2. Postgres SSL enforcement enabled;
3. database/pooler network restrictions limited to the approved hardened-host egress CIDR set.

Current connected tooling can confirm project health and database/catalog state, but does not expose authoritative read/write controls for all three settings. Their state remains **unknown** until verified through the Dashboard or an appropriately scoped Management API path.

The preflight is fail-closed: unavailable/denied reads remain unknown; SSL changes are isolated because they restart the database; network restrictions are not applied before the actual hardened-host egress CIDRs are known and stable; no world-open placeholder CIDR is accepted; management changes are not batched with C2 DDL.

## Hardened-host candidate

PR #140 selected the first later qualification candidate:

- Amazon Lightsail Linux/Unix Micro 1 GB;
- Asia Pacific (Tokyo), `ap-northeast-1`;
- 2 vCPU, 1 GB RAM, 40 GB SSD, 2 TB transfer;
- current published maximum bundle price: **USD 7/month**;
- attached Lightsail static IPv4: no additional charge.

No host has been provisioned and no AWS cost has been incurred.

Cheaper 512 MiB options are not the primary candidate because they leave materially less runtime/security-update headroom; the reviewed DigitalOcean option is also Singapore rather than Tokyo. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target; qualify the next reviewed size from evidence.

Lightsail's platform firewall does not supply the required outbound restriction, so the eventual host must enforce default-deny egress locally.

## Host hardening review in progress

Current branch: `agent-secret-host-hardening-review-v1-20260930`.

Review-only artifacts now prepared:

- `SECRET_CUSTODY_HOST_HARDENING_REVIEW.md`;
- `review/lightsail_host_preflight.sh`;
- `tests/test_secret_custody_host_hardening_review.py`;
- regression wiring for the new review boundary.

The preflight script is intentionally offline and read-only. It checks the expected Linux/systemd/cgroup-v2 shape, required host tools, reviewed 1 GB-class memory floor, swap-disabled state and unexpected wildcard listeners. It does not install packages, change the firewall, restart services, edit system state, contact AWS/Supabase/GitHub or read secret values.

The reviewed live-host progression is H0-H7: immutable candidate/price check, local read-only preflight, separate administrator/filesystem hardening, inbound restriction, OS-level default-deny outbound policy, verify-full TLS/database qualification, resource/reboot/recovery qualification, and only then the later C2/C3 activation gates.

The future host begins **untrusted / no-secret**. Passing host hardening by itself does not authorize C2 DDL or any credential use.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable.

Free is **not** approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or another explicitly reviewed solution that provides equivalent availability.

Do not generate artificial keepalive traffic and call that an availability guarantee. Do not upgrade merely for code review or no-secret testing.

For the hardened host, create no paid resource until live provisioning is specifically authorized. When that boundary arrives, start with exactly one USD 7/month candidate, qualify it with synthetic/no-secret inputs, and destroy it promptly if rejected.

## Next work / next boundary

The next safe sequence is:

1. merge the host-hardening review only if exact-head CI is clean;
2. before any paid provisioning, re-check the selected Lightsail price and Tokyo availability;
3. require a specific live-provision authorization before creating the instance/static IP;
4. provision exactly one candidate and run only no-secret host qualification first;
5. apply reviewed hardening only after its mutating package is separately reviewed;
6. verify static egress, OS-level default-deny egress, TLS `verify-full`, reboot/recovery and memory headroom;
7. use that verified static egress only when configuring the Supabase network restriction;
8. verify Data API disabled and SSL enforcement enabled, changing each separately only if required;
9. require fresh explicit authorization before applying C2 DDL to the live custody project;
10. use only clearly synthetic credential material for C3;
11. require a separate availability/cost decision plus explicit authorization before C4 real credential activation.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

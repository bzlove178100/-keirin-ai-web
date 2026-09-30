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

PR #139 (`Add fail-closed custody management-plane preflight`) merged to `main` as:

`f5761ae815a45a7a24c67d3866fc7aae6ad07b0f`

Its exact-head and post-merge checks passed, including:

- `keirin-ai regression`;
- `collection progress UI regression`;
- `agent runtime read-only smoke`;
- `agent checkpoint PostgreSQL contract`;
- synthetic host-limits qualification;
- TLS/restart, row-lock/process-deadline, logging and pgAudit redaction checks;
- Pages build/deployment.

The PostgreSQL contract still covers the co-resident actual application stack, fail-closed lease/trust/hostname rejection, real row-lock/process-deadline behavior, hardened host limits, TLS/restart recovery, log-policy checks and pgAudit parameter-redaction checks.

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

The current live security-advisor check returned zero lints. This is supplementary evidence only; it does not prove the management-plane gates below.

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

Current connected tooling can confirm project health and database/catalog state, but does not expose authoritative read/write controls for all three settings. Their state therefore remains **unknown** until verified through the Dashboard or an appropriately scoped Management API path.

The preflight is fail-closed:

- a denied or unavailable read is `unknown`, not safe;
- SSL-enforcement changes are isolated because they restart the database;
- network restrictions are not applied until the actual hardened-host egress IPv4/IPv6 CIDRs are known and stable;
- no world-open placeholder CIDR is accepted;
- management configuration is not batched with C2 DDL.

## Hardened-host cost review

`SECRET_CUSTODY_HOST_CANDIDATE.md` records the current lowest-cost candidate that preserves a reasonable qualification margin.

First candidate for later qualification:

- Amazon Lightsail Linux/Unix Micro 1 GB;
- Asia Pacific (Tokyo), `ap-northeast-1`;
- 2 vCPU, 1 GB RAM, 40 GB SSD, 2 TB transfer;
- current published maximum bundle price: **USD 7/month**;
- attached Lightsail static IPv4: no additional charge.

No host has been provisioned and no AWS cost has been incurred.

The cheaper USD 5 Lightsail 0.5 GB and USD 4 DigitalOcean 512 MiB shapes are not selected as the primary candidate because they leave materially less runtime/security-update headroom; the DigitalOcean comparison is also Singapore rather than Tokyo. GitHub static-IP larger runners require a substantially different paid-plan boundary, and the reviewed Hetzner Singapore entry is currently higher cost.

The USD 7 candidate still must pass live synthetic/no-secret capacity, TLS, restart, egress, static-IP and firewall qualification. If 1 GB is insufficient, do not weaken safeguards; move to the next reviewed size.

Lightsail's platform firewall does not restrict outbound traffic, so the host must enforce a default-deny OS-level egress policy before any custody credential or Vault material exists.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable.

Free is **not** approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or another explicitly reviewed solution that provides equivalent availability.

Do not generate artificial keepalive traffic and call that an availability guarantee. Do not upgrade merely for code review or no-secret testing.

For the hardened host, do not create multiple paid candidates. Start with one USD 7/month candidate only when live host qualification is explicitly authorized; destroy it promptly if rejected. Move to a larger size only from evidence, not precautionary over-provisioning.

## Next work / next boundary

The next safe sequence is:

1. merge the hardened-host candidate review if exact-head CI is clean;
2. before any paid provisioning, re-check the selected provider's current price and Tokyo availability;
3. require a specific live-provision authorization before creating the Lightsail instance/static IP;
4. provision exactly one candidate and harden it using synthetic/no-secret inputs only;
5. verify actual static egress, OS-level default-deny egress, TLS `verify-full`, restart/recovery and memory headroom;
6. use that verified static egress only when authoritatively configuring the Supabase network restriction;
7. verify Data API disabled and SSL enforcement enabled, changing each separately only if required;
8. require fresh explicit authorization before applying C2 DDL to the live custody project;
9. after C2 and rollback qualification, use only clearly synthetic credential material for C3;
10. require a separate availability/cost decision plus explicit authorization before C4 real credential activation.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

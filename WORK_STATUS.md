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

PR #143 (`Synchronize verified status through provisioning review`) merged to `main` as:

`c2e247fb65740ccfc5f82b60b102a0f14d05a73d`

Its exact-head CI passed, and post-merge `main` completed five workflows with zero failed and zero in-progress runs for that merge SHA, including collection UI, regression, read-only runtime, PostgreSQL/host contract and Pages paths.

The PostgreSQL contract continues to cover the co-resident application stack, fail-closed lease/trust/hostname rejection, real row-lock/process-deadline behavior, hardened host limits, TLS/restart recovery, log-policy checks and pgAudit parameter-redaction checks.

## Runtime staging project

Existing runtime/checkpoint staging remains `keirin-ai-staging` in `ap-northeast-1`. Provider/runtime execution gates, prediction DB writes and external race-data fetching remain OFF.

Do not repurpose this shared application staging Vault for real agent refresh-secret custody. The 2026-09-30 Phase A inventory confirmed `service_role` can directly access decrypted Vault data in that project.

## Secret-custody project

A dedicated `keirin-ai-secret-custody` project exists in `ap-northeast-1` (Tokyo). The organization plan remains Free and the project-creation cost check returned 0 per month. The project was `ACTIVE_HEALTHY` at the last live check.

No paid add-on, database password, Vault secret, binding row, provider credential, Edge Function or hosted worker has been created for the custody path.

## C0 / C1 complete boundary

`SECRET_CUSTODY_C0_C1_EVIDENCE.md` records the dedicated-project provisioning and catalog-only inventory. The observed database is PostgreSQL 17.6 family, primary, with `supabase_vault` 0.3.1. Proposed private roles/schema were absent. No secret row/value/name/description or provider credential was read and no DDL/DML was submitted during C1.

Project isolation, not revocation of Supabase-managed platform privileges, is the selected blast-radius boundary.

## C2 review artifacts complete

PR #138 added `SECRET_CUSTODY_C2_REVIEW.md`, the candidate/rollback SQL outside `supabase/migrations`, and regression guards. The reviewed model retains the dedicated LOGIN host / NOLOGIN broker split, private metadata schema, forced RLS, exact read/CAS functions, no runtime `vault.create_secret` capability, no password, no binding row and no secret provisioning.

**C2 has not been applied to Supabase.**

## Management-plane preflight

PR #139 added `SECRET_CUSTODY_MANAGEMENT_PLANE_PREFLIGHT.md` with three hard gates:

1. Data API disabled;
2. Postgres SSL enforcement enabled;
3. database/pooler network restrictions limited to the approved hardened-host egress CIDR set.

Their authoritative live state remains unknown until verified through the Dashboard or an appropriately scoped Management API path. Unavailable/denied reads remain unknown; no world-open placeholder CIDR is accepted; management changes are not batched with C2 DDL.

## Hardened-host candidate

PR #140 selected Amazon Lightsail Linux/Unix Micro 1 GB in Tokyo (`ap-northeast-1`) as the first later qualification candidate: 2 vCPU, 1 GB RAM, 40 GB SSD, 2 TB transfer, reviewed maximum bundle price USD 7/month, with an attached static IPv4.

The public AWS documentation was re-checked on 2026-09-30 before the provisioning review. Exact Tokyo control-plane availability and the live Ubuntu LTS blueprint ID still require an authenticated AWS session immediately before creation.

No host has been provisioned and no AWS cost has been incurred. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target.

## Host hardening and provisioning reviews complete

PR #141 added the read-only H0-H7 hardening qualification review and offline `review/lightsail_host_preflight.sh`. PR #142 added the fail-closed provisioning review and `review/lightsail_provisioning_manifest.template.json` with `authorized_for_live_create=false`.

The future host begins **untrusted / no-secret**. Passing repository review or host hardening by itself does not authorize C2 DDL or credential use.

## Hardening package review in progress

Current branch: `agent-secret-host-hardening-package-review-v1-20260930`.

Review-only artifacts now prepared:

- `SECRET_CUSTODY_HOST_HARDENING_PACKAGE_REVIEW.md`;
- `review/secret_custody_host_hardening.plan.json`;
- `review/validate_secret_custody_host_hardening_plan.py`;
- `tests/test_secret_custody_host_hardening_package_review.py` plus regression wiring.

The plan is declarative data, not an executable host mutation script. It fixes the reviewed host shape, no-secret preconditions, dedicated non-login runtime identity, root-owned/read-only filesystem boundary, systemd sandbox requirements, default-deny runtime egress, metadata-only logging, post-reboot/resource checks, disabled runtime/provider/prediction gates and a structural pre-credential rollback boundary.

`authorized_for_live_apply=false` is mandatory. The validator rejects world-open CIDRs, credential-like literals, executable package/firewall/service/user mutation markers in plan data, enabled runtime gates, or any secret-policy field set true.

No AWS, host, Supabase, Vault, provider, prediction or race-data state is changed by this branch.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable. Free is not approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or an equivalent separately reviewed solution.

For the hardened host, start with exactly one USD 7/month candidate only after a specific live-provision authorization, qualify it with synthetic/no-secret inputs, and destroy it promptly if rejected. Do not keep multiple paid hosts running for convenience.

## Next work / next boundary

The next safe sequence is:

1. merge the hardening-package review only if exact-head CI is clean;
2. in an authenticated AWS control-plane session, confirm Tokyo availability, exact Ubuntu LTS blueprint and displayed Micro 1 GB price before creation;
3. require a specific live-provision authorization before creating the instance/static IP;
4. create exactly one candidate and attach exactly one static IPv4;
5. run only the read-only/no-secret H1 preflight first;
6. compare actual host facts to the reviewed hardening plan before any mutation;
7. require a separate live-hardening authorization before applying any mutating host package;
8. verify static egress, OS-level default-deny egress, TLS `verify-full`, reboot/recovery and memory headroom before any credential exists;
9. use that verified static egress only when configuring the Supabase network restriction;
10. verify Data API disabled and SSL enforcement enabled, changing each separately only if required;
11. require fresh explicit authorization before applying C2 DDL to the live custody project;
12. use only clearly synthetic credential material for C3;
13. require a separate availability/cost decision plus explicit authorization before C4 real credential activation.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

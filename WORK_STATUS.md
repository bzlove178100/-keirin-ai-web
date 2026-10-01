# Work status

Updated: 2026-10-01 (Asia/Tokyo).

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

The verified base before this account-boundary update is:

`b03ee168390ef2d98e432cbae80638d11572875c`

PR #151 is merged and contains the GitHub OIDC read-only observation package. PR #149 previously synchronized the AWS-observation handoff after PR #148.

PR #149 exact-head CI passed: collection progress UI regression, agent runtime read-only smoke, keirin-ai regression, and agent checkpoint PostgreSQL contract all completed successfully. When resuming, resolve the current `main` from GitHub rather than treating an embedded SHA as permanently current.

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

The provider boundary was re-checked on 2026-10-01. Lightsail remains the first candidate: current public documentation still shows Tokyo support and the USD 7 Micro 1 GB public-IPv4 bundle shape. Railway and Render do not currently provide a lower-friction equivalent for this design's Tokyo + stable-egress requirement, and DigitalOcean has no Tokyo region.

AWS account bootstrap is now complete. The user created the Proof of Concept account, upgraded it to the paid usage model, activated advanced features, and created the `ai-agent-team` management boundary. A USD 10 monthly AWS Budget exists and its charge-type filter excludes Credit and Refund so AWS usage remains visible while promotional credits are available. No Lightsail host or static IP has been provisioned. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target.

## Host safety reviews complete

PR #141 added the read-only H0-H7 hardening qualification review and offline `review/lightsail_host_preflight.sh`. PR #142 added the fail-closed provisioning review and `review/lightsail_provisioning_manifest.template.json` with `authorized_for_live_create=false`. PR #144 added the declarative hardening package review, offline validator and regression guards with `authorized_for_live_apply=false`. PR #145 added fail-closed recovery/rollback review artifacts with `authorized_for_live_recovery=false`. PR #146 added the read-only AWS control-plane observation review and sanitized observation template with `authorized_for_live_create=false`.

The future host begins **untrusted / no-secret**. Passing repository review or host hardening by itself does not authorize C2 DDL or credential use.

The hardening package is declarative data, not an executable host mutation script. The recovery plan keeps the runtime disabled and host no-secret on preflight, hardening, network/TLS, capacity or reboot/recovery failure. Automatic AWS destruction/resize/reboot/snapshot/replacement, automatic firewall relaxation/egress widening, protected Supabase/Vault/provider/prediction/race-data mutations, insecure TLS/plaintext fallback and credential introduction during recovery are forbidden by the reviewed contracts.

## AWS GitHub OIDC read-only automation

Manual AWS console navigation is no longer the preferred observation path.

`AWS_GITHUB_OIDC_READONLY_OBSERVATION.md`, `review/aws_github_oidc_readonly_role.yaml`, `review/aws_lightsail_readonly_observation.sh` and the manual-dispatch GitHub Actions workflow define a short-lived OIDC path that can inspect the Lightsail Tokyo catalog without long-lived AWS access keys.

The reviewed role is restricted to GitHub owner/repository immutable IDs, branch `main`, audience `sts.amazonaws.com`, and exactly three Lightsail catalog reads: `GetRegions`, `GetBlueprints`, and `GetBundles`. It has no Lightsail mutation permission.

The public CloudShell path in Tokyo failed during bootstrap with an environment/permission error. Do not create a CloudShell VPC environment for this observation. The OIDC path supersedes repeated CloudShell/console attempts.

One bounded bootstrap remains before the workflow can run: create the reviewed CloudFormation stack in the Proof of Concept AWS account, then store its role ARN as the GitHub Actions secret `AWS_READONLY_ROLE_ARN`. No AWS account identifier or credential may be committed to the repository.

The 2026-10-01 session is blocked before verified AWS application: Work Cloud Browser returned `Site Unavailable`; the Root-attached regional SCP restricts Tokyo despite account-level activation; and full-text replacement in the phone policy editor could not be completed. A narrowly scoped private SCP draft was approved, but successful saving/read-back is unverified. The existing `builderid:*` validation finding is unresolved. No stack creation, role-ARN secret registration or live workflow success has been verified. See `WORK_RESUME.md` for the exact restart boundary; do not repeat Cloud Browser/CloudShell/mobile-editor attempts.

Offline observation hardening now requires exact Tokyo before any AWS call, explicitly active catalog entries, an identifiable Ubuntu LTS OS blueprint, and an identifiable matching bundle with one public IPv4 and a finite nonnegative numeric price. Synthetic stub tests cover missing/malformed facts and API failure without AWS credentials or network calls. These tests are not evidence of live catalog availability or AWS policy validation.

## AWS control-plane observation review complete

`SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json` define the next live observation boundary. The template fixes the expected region/host shape/price ceiling while leaving every live observation value unset. It keeps `authorized_for_live_create=false`, rejects automatic size/region substitution, forbids sensitive account/key/IP/credential material and keeps every runtime/provider/prediction gate disabled.

The next authenticated AWS session is limited to observing exact Tokyo availability, Ubuntu LTS blueprint identifier, matching bundle shape, displayed monthly price and static-IPv4 availability/pricing. Unknown, ambiguous or mismatching values fail closed. Passing observation still requires a separate explicit live-provision instruction before any AWS resource is created.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable. Free is not approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or an equivalent separately reviewed solution.

For the hardened host, start with exactly one USD 7/month candidate only after a specific live-provision authorization, qualify it with synthetic/no-secret inputs, and destroy it promptly if rejected after a separately authorized live cleanup. Do not keep multiple paid hosts running for convenience.

## Next work / next boundary

The next safe sequence is:

1. retain the merged GitHub OIDC package and resolve the documented access/SCP blocker through a usable authorized path, verifying saved state rather than repeating unsuccessful phone editing;
2. in the Proof of Concept AWS account, create only the reviewed CloudFormation OIDC stack;
3. store only the resulting role ARN in the GitHub Actions secret `AWS_READONLY_ROLE_ARN`; do not create an AWS access key;
4. run the manual `aws lightsail read-only observation` workflow;
5. require Tokyo `ap-northeast-1`, an active Ubuntu Linux/Unix blueprint, and an active bundle matching 2 vCPU / 1 GiB / 40 GiB / 2 TB at no more than USD 7;
6. keep static IPv4 allocation untested until provisioning because a live allocation probe would be mutating;
7. stop if any required catalog value is unknown, mismatched or over budget;
8. require a separate specific live-provision authorization before creating the instance/static IP;
9. create exactly one candidate and attach exactly one static IPv4;
10. run only the read-only/no-secret H1 preflight first;
11. compare actual host facts to the reviewed hardening and recovery plans before any mutation;
12. require a separate live-hardening authorization before applying any mutating host package;
13. verify static egress, OS-level default-deny egress, TLS `verify-full`, reboot/recovery and memory headroom before any credential exists;
14. use that verified static egress only when configuring the Supabase network restriction;
15. verify Data API disabled and SSL enforcement enabled, changing each separately only if required;
16. require fresh explicit authorization before applying C2 DDL to the live custody project;
17. use only clearly synthetic credential material for C3;
18. require a separate availability/cost decision plus explicit authorization before C4 real credential activation.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

## Catalog command error privacy (2026-10-01)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made. OIDC stack creation, role secret setup, the pending SCP save, and live observation remain unverified; Cloud Browser/CloudShell retries remain paused.

## OIDC template preflight (2026-10-01)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The next live dependency is still an available authorized AWS path and read-back of the pending policy state. Do not repeat the blocked browser/CloudShell attempts or failed phone editing instructions. No stack, role secret, or live observation was verified by this offline work.

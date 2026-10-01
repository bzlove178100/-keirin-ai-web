# Work status

## Current boundary: H3 host readback failed; scoped IPv6 parser correction

Updated: 2026-10-02 01:56 JST evidence (Asia/Tokyo).

The user's IMG_8929 shows the immutable PR #171 observer at commit `60b435c8e2e04d9dc14bbc5070e867cdfa8ad996`, SHA-256 `d94175d03b18fa167fa98b76379d62ef8df178e4a7fe21e899437a93a08ef572`, ending with `STOP NETWORK_READBACK_UNAVAILABLE` and `RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION`, followed by the prompt. This is an unsuccessful host observation. No host facts were emitted; effective network policy remains unknown. The screenshot cannot identify the failed stage or exception type. Do not repeat that unchanged command or claim a host configuration failure.

A concrete observer defect is reproduced locally: `ss` can render scoped IPv6 as `[fe80::1234]%interface:546`. The old `strip("[]").split("%", 1)[0]` leaves a closing bracket and raises ValueError. The iproute2 v6.1.0 source brackets the address before appending the interface scope, confirming that this is a legitimate representation. The original tests exercised only scope inside brackets and real unscoped loopback sockets. This is a verified parser defect and a plausible explanation of the live STOP, **not yet a confirmed live root cause**.

The correction supports both bracket/scope placements and scoped wildcards, while rejecting malformed brackets, duplicate/empty zones and invalid addresses. It also attributes read/parse failures to fixed stage and category codes without exception text, raw addresses or command diagnostics. No read is skipped; facts stay buffered until complete success. The fixed read-only commands, byte/time bounds, no-mutation scope and all disabled gates remain unchanged.

Sixteen offline tests cover the correction and error attribution. Mandatory existing CI adds an actual scope-bearing IPv6 UDP socket inside its disposable isolated network namespace, alongside nft and IPv4/IPv6 checks. All five workflows must pass on the correction commit before merge/readback and a replacement immutable phone command. CI success alone does not resolve the live incident. One changed-code phone run should either complete with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION` or provide a new fixed STOP/STAGE pair; diagnose that pair rather than repeating unchanged commands.

H1, H2a recovery/installation, H2b, H2c and the ten H2d PASS records at 01:38 JST remain completed in their measured scopes (PR #170). Do not repeat provisioning, login/key/keyboard setup, rollback/apply or those completed probes. The H2a placeholder remains inactive. Work has no independent host/AWS session and the user supplies the live terminal evidence.

After one successful host readback, inspect the current Lightsail IPv4 and IPv6 firewall entries from the existing phone session. The earlier SSH edit screenshots did not expose the complete saved policy. Unknown/nonempty host rules require private review; do not flush or replace them. No IAM expansion, new inventory workflow dispatch, firewall change, stress or reboot follows from this correction. Preserve phone SSH and the recorded manual/template difference.

See [network readback review](SECRET_CUSTODY_HOST_NETWORK_READBACK_REVIEW.md). All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Local IPC/syscall, application capacity, complete host/cloud ingress and default-deny egress, TLS, whole-controller and reboot recovery qualification remain pending. The host stays untrusted/no-secret.

## Historical failed H2a attempt and correction: H2a authorized; first apply failed; correction under validation

Updated: 2026-10-02 00:06 JST evidence (Asia/Tokyo).

The user explicitly said `適用して` at 2026-10-01 23:56:43 JST after the exact H2a identity/files/inactive-unit scope was presented. That authorization remains valid for diagnosis, bounded recovery and corrected application within the same scope; **do not ask for the same permission again**. It does not activate runtime, provider, credentials, networking changes or any other gate.

PR #166 merged offline preparation. The user's first live command pinned commit `5cc75aa40523e405ccd0a6515386d3a41eeb886d` and script SHA-256 `50a92a2b0c4585cc965a91faf737d81d337408573cf2668dd26dc49a825473e1`. At 00:00 JST it returned `STOP HOST_COMMAND_FAILED` / `RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_APPLY`. This was **not a successful installation**.

At 00:06 JST screenshot IMG_8924 confirmed: the receipt directory exists; the reserved code/config directories and unit file are absent; dedicated user/group lookups each return 2; systemd reports not-found/inactive, empty fragment/drop-ins/unit-file state, and show exit 0. Receipt contents have not independently been read back. The failure is consistent with the invalid `useradd --key CREATE_MAIL_SPOOL=no` argument found in our implementation. The prior mocked account tests missed the real parser boundary. The correction removes that invalid login.defs override; system accounts already skip mail creation. Fixed stage-specific command errors retain diagnostic privacy.

[H2a review and recovery](SECRET_CUSTODY_HOST_H2A_REVIEW.md) describes the defect, primary source and new real CLI test: installed Ubuntu 24.04 account tools target only a disposable chroot database, while the manager/process adapter remains synthetic. It reproduces the invalid command, checks receipt-only partial state, then exercises bounded rollback, corrected apply and verification. Require this CI step and existing regression checks to pass on the exact correction commit before merge or phone execution. Local Work has only UID/GID 0 and rejects the account CLI audit interface; it cannot substitute for this CI gate.

After CI/merge, use an immutable, hash-checked corrected script. Run its existing ownership-checked rollback once, then apply only if rollback succeeds; verify afterwards. Preserve the existing receipt schema for compatibility. No blind recursive removal, unchanged retry, approval bypass, password/key request or firewall widening. Any new STOP requires diagnosis. Successful offline tests are not live success; await the phone result `INSTALLED_DISABLED_NOT_QUALIFIED` before recording installation.

The candidate remains **untrusted / no-secret**; H2-H7 effective qualification and all runtime/credential gates remain pending/OFF. Work has no independently verified AWS/SSH session. The user's Termius connection works. Do not repeat provisioning, cost approval, IAM/bootstrap, inventory, key import, keyboard setup or H1.

## Previous milestone: creation and H1 completed

Updated: 2026-10-01 23:23 JST (Asia/Tokyo).

The user's phone screenshots confirm completion of the approved single Tokyo candidate and attached static IPv4, successful native Termius SSH login, command execution and the read-only H1 result `PREFLIGHT_OK_NO_MUTATION` with zero warnings/failures. See [creation and H1 evidence](SECRET_CUSTODY_HOST_H1_EVIDENCE.md) for the sanitized chronology, immutable script identity and limits.

The host remains **untrusted / no-secret**. H2-H7, workload capacity, effective sandbox/default-deny egress, static egress, TLS and reboot/recovery qualification are pending. H2a authorization, correction and successful installation are recorded above; effective qualification remains pending. No runtime/provider activation or custody secret use follows from H1.

Do not repeat creation, its cost approval, IAM/bootstrap, inventory, phone browser keyboard attempts, key import or H1 just to resume. The existing phone Termius path works. Work has no independently verified AWS/host session; use existing evidence and connectors within their actual permissions.

The phone administration change added one observed-source IPv4 /32 for SSH while preserving browser SSH IPv4 access. Full post-save firewall read-back remains unverified, and the original CloudFormation template still describes browser-only ingress. Review this manual difference before any stack update; keep IPs/key material private.

The dated sections below are historical observations at their stated stage. Their earlier zero-resource counts and untested-login statements are superseded by the evidence above, not instructions to repeat those operations.

## Scoped creation authorization (historical; operation now complete) — 2026-10-01 20:56:49 JST

The user replied `続けて` directly to the explicit approval request for the presented candidate file, one Tokyo Ubuntu 24.04 / 1 GB / 2 vCPU / 40 GB instance, USD 7/month base bundle (tax/transfer overage separate), one attached static IPv4, browser-SSH-only initial ingress and retention of successfully created resources on failure. In that conversational context, this authorizes proceeding with that exact one-candidate creation. Do not ask the same cost/configuration question again.

The approved template remains blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its default and repository metadata remain non-authorizing; the live parameter may now be set to `ONE_CANDIDATE_USD7_APPROVED` for this approved operation. Proposed inputs remain stack `keirin-ai-custody-h1`, instance `keirin-custody-h1`, static IP `keirin-custody-h1-ip`, zone `ap-northeast-1a`, blueprint `ubuntu_24_04`, bundle `micro_3_0`, and existing default key `LightsailDefaultKeyPair`.

Authorization is not completion. No CREATE change set, instance, static IP or SSH login has been performed by this turn. The next required evidence is the authenticated intended-account/Tokyo context, absent proposed stack name, current selected blueprint/bundle and the actual resolved change set with exactly two Add actions. Verify preserve-successful-resources and deletion-policy behavior before Execute. A matching actual proposal can proceed under the existing approval; a different scope, cost, account, ingress or failure behavior requires resolving that difference before execution.

The usable AWS session is on the user's phone; Work has no verified AWS control-plane session and the existing GitHub role cannot provision. Guide the existing phone session without retrying the known Work login failure. Do not repeat inventory/bootstrap, expand IAM, create/download keys or introduce extra resources. Hosted execution, real credentials, hardening, Supabase changes and production prediction remain outside this authorization.

## Creation configuration and public-price review — 2026-10-01 (before approval)

At the earlier offline review, the paid scope was fully specified but not yet authorized or executed; subsequent authorization is recorded above. AWS's [current public pricing](https://aws.amazon.com/lightsail/pricing/) was rechecked on 2026-10-01: Linux/Unix with public IPv4, 1 GB memory, 2 vCPU, 40 GB disk and 2 TB transfer is USD 7/month. The [billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html) confirms no additional static-IP charge while attached, and USD 0.005/hour when unattached for more than one hour. Taxes, currency conversion and transfer overage are outside the bundle ceiling; no free-trial credit is assumed.

The exact candidate remains unchanged from main `16c31f91a4205991c28ac2a33e8c64678a2a4f29`, blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its two resources are CustodyCandidate and CustodyStaticIp. The proposed new stack name is `keirin-ai-custody-h1`; stack-name absence and independent account identity are still unverified. The selected zone is `ap-northeast-1a` and the existing key parameter is `LightsailDefaultKeyPair`, observed by inventory run #2. Blueprint/bundle availability evidence remains the 18:28 catalog run; public-price verification is not a new AWS API observation.

At this earlier review point, the cost decision was still pending and the acknowledgement remained NOT_AUTHORIZED. The subsequent 20:56:49 JST authorization is recorded above. The actual CREATE change set and account/stack checks remain pending; do not confuse approval with execution or GitHub authentication with AWS access.

## Corrected inventory verified on 2026-10-01 (historical, before creation)

At 20:37:39 JST the user explicitly authorized one additional corrected read-only inventory run. [Inventory run #2](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36856726931) was dispatched exactly once from main `de7cd0b97bb009f5f9394512f94bf5be33d5251b` (PR #161 merged). Job `110350863079` completed successfully, including OIDC authentication and all three inventory reads. The version 2 result was emitted at 11:39:38 UTC / 20:39:38 JST.

| Observation | Verified result |
| --- | --- |
| Region | ap-northeast-1 |
| Instances / static IPs / key pairs | 0 / 0 / 1 |
| Proposed instance / static-IP name collisions | false / false |
| Tokyo default key present | true |
| Review reasons | empty |
| Key login / independent account identity / stack-name inventory | Not verified |
| Live creation authorized | false |

The corrected default-key classifier is now verified against AWS metadata. This resolves the earlier default-key identity uncertainty; version 1's absence flag remains invalid historical evidence. No key was created or downloaded and no private key material was read. Metadata presence does not verify SSH login.

Both authorized inventory runs are complete. Do not dispatch a third run or repeat the IAM/bootstrap setup automatically. Next, verify the intended account, proposed stack name and current blueprint/bundle/price before preparing the exact two-resource CREATE change set for separate approval. No paid host/IP creation, provisioning permission, runtime activation or Supabase change was authorized by this inventory execution.

## Concrete host proposal prepared offline (historical)

The user authorized the exact Tokyo GetInstances/GetStaticIps/GetKeyPairs IAM update plus one inventory run on 2026-10-01. The reviewed single-role, non-replacement change set preserved trust and all other role properties. CloudFormation reached UPDATE_COMPLETE at 19:52:49 JST. Separate post-update IAM policy/trust read-back was not performed.

[Inventory run #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36852494617) succeeded on main `a713b6d57199975e13c32edd84cee9d2ed2da602` at 19:59:23 JST: Tokyo instances 0, static IPs 0, key pairs 1; both proposed name-collision flags false. This consumed the first one-run authorization; the separately authorized corrected run #2 is recorded above.

Version 1 used a download filename stem for the default-key match; its false default-key flag/reason remains invalid as absence evidence. Version 2 corrected the API name to `LightsailDefaultKeyPair` with independent literal regression fixtures, passed 33 local tests and all five applicable CI workflows, and is now verified by run #2. The existing Tokyo default key was observed without an IAM expansion. Full evidence and retry/stop conditions are in `AWS_LIGHTSAIL_INVENTORY_REVIEW.md` and `WORK_RESUME.md`.

`review/aws_lightsail_candidate.json` proposes exactly one Tokyo Ubuntu 24.04 LTS / micro_3_0 candidate and one attached static IPv4. The planned names are keirin-custody-h1 and keirin-custody-h1-ip, not verified existing resources. The USD 7/month figure is the observed bundle price, subject to a fresh pre-execution price check.

The template rejects its default acknowledgement, wrong region or mismatching expected account. It requires an existing Tokyo Lightsail key pair, requests only browser-SSH source alias ingress, embeds no launch script/credentials and retains both resources on stack removal. The review explains failure-retention costs, change-set review, actual firewall verification and separately authorized cleanup. Local cfn-lint 1.57.1 passed with no findings and 10 candidate safety-contract tests passed; the offline CI repeats these checks.

The host proposal remains offline: no host, static IP or key was created. The authorized IAM update and both inventory runs are complete. Default-key identity is resolved; independent account/stack checks and deployment permissions remain unresolved. The role has six read actions (three catalog plus three Tokyo inventory), with no provisioning permission. Read `SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md` for the subsequent execution sequence.

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
- one paid candidate and attached static IPv4 exist; H1 passed, full hardening is pending.

Agent-only checkpoint/activity persistence and queue coordination in `keirin-ai-staging` were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

The live observation ran against main `f08bfbb3ed59478653f9055757b138e7c0141dcf` (PR #157 merged). PR #157 head `e21f161075908fac10e938a56c11ab6440640cc5` passed all five applicable workflows: collection progress UI regression, agent runtime read-only smoke, aws observation offline contract, keirin-ai regression and agent checkpoint PostgreSQL contract.

PR #151 introduced the reviewed OIDC read-only observation package; #152 added catalog-error privacy and #153 added offline CloudFormation template validation. The live run is separate evidence that the deployed OIDC role and catalog reads worked.

Resolve current main from GitHub on the next resumption; embedded SHAs are historical evidence, not a permanently current branch pointer. The PostgreSQL contract retains the application stack, lease/trust/hostname, row-lock/deadline, TLS/restart recovery and audit-redaction checks.

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

AWS account bootstrap is now complete. The user created the Proof of Concept account, upgraded it to the paid usage model, activated advanced features, and created the `ai-agent-team` management boundary. A USD 10 monthly AWS Budget exists and its charge-type filter excludes Credit and Refund so AWS usage remains visible while promotional credits are available. The single candidate and attached static IPv4 have now been created; H1 passed. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target.

## Host safety reviews complete

PR #141 added the read-only H0-H7 hardening qualification review and offline `review/lightsail_host_preflight.sh`. PR #142 added the fail-closed provisioning review and `review/lightsail_provisioning_manifest.template.json` with `authorized_for_live_create=false`. PR #144 added the declarative hardening package review, offline validator and regression guards with `authorized_for_live_apply=false`. PR #145 added fail-closed recovery/rollback review artifacts with `authorized_for_live_recovery=false`. PR #146 added the read-only AWS control-plane observation review and sanitized observation template with `authorized_for_live_create=false`.

The created candidate remains **untrusted / no-secret** after H1. Passing repository review or host hardening by itself does not authorize C2 DDL or credential use.

The hardening package is declarative data, not an executable host mutation script. The recovery plan keeps the runtime disabled and host no-secret on preflight, hardening, network/TLS, capacity or reboot/recovery failure. Automatic AWS destruction/resize/reboot/snapshot/replacement, automatic firewall relaxation/egress widening, protected Supabase/Vault/provider/prediction/race-data mutations, insecure TLS/plaintext fallback and credential introduction during recovery are forbidden by the reviewed contracts.

## AWS GitHub OIDC read-only automation

`AWS_GITHUB_OIDC_READONLY_OBSERVATION.md`, `review/aws_github_oidc_readonly_role.yaml`, `review/aws_lightsail_readonly_observation.sh` and the manual-dispatch workflow define the short-lived OIDC observation path. The deployed role was successfully assumed in run #1 and the three catalog calls passed.

The reviewed role is restricted to the immutable GitHub owner/repository IDs, branch main, audience sts.amazonaws.com, and the three catalog actions `GetRegions`, `GetBlueprints`, `GetBundles`. The separately approved update added only Tokyo `GetInstances`, `GetStaticIps`, `GetKeyPairs`. It has no Lightsail mutation permission. Do not widen it for provisioning without a separate review/authorization.

CloudFormation/SCP and browser/app troubleshooting are completed history for this boundary. Do not repeat failed CloudShell/mobile-editor paths or recreate the stack/secret. Offline checks still enforce exact Tokyo, active identifiable Ubuntu LTS, the matching bundle shape/public IPv4 and a finite nonnegative price at or below USD 7. Passing catalog reads does not verify allocation, host safety or provisioning permissions.

## AWS control-plane observation review complete

`SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json` define the reviewed observation boundary. The template fixes the expected region/host shape/price ceiling while leaving every live observation value unset. It keeps `authorized_for_live_create=false`, rejects automatic size/region substitution, forbids sensitive account/key/IP/credential material and keeps every runtime/provider/prediction gate disabled.

The initial authenticated catalog observation passed; see the verified values above. Static IPv4 creation/attachment was subsequently observed through the phone console; see the H1 evidence. Unknown, ambiguous or mismatching future values fail closed. Passing observation still requires a separate explicit live-provision instruction before any Lightsail instance or static IP is created.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable. Free is not approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or an equivalent separately reviewed solution.

Exactly one USD 7/month candidate has been created under the scoped approval. Continue qualification with synthetic/no-secret inputs; a rejection requires a separately reviewed and authorized cleanup decision. Do not keep multiple paid hosts running for convenience.

## Next work / next boundary

1. Creation, native SSH and read-only H1 are complete. Use `SECRET_CUSTODY_HOST_H1_EVIDENCE.md`; do not recreate or re-run setup without a changed condition.
2. H2a installation and H2b live verification are complete. Finish exact-head CI for bounded H2c synthetic memory verification and use the existing Termius session once; preserve the fixed inactive installation and all gates.
3. Confirm complete relevant current firewall rules before H3/H4; preserve the bounded phone/browser administration path. The manual /32 source differs from the original browser-only template.
4. Qualify effective sandbox/resource limits, no-secret capacity, default-deny egress, verified static egress, TLS verify-full and reboot/recovery before introducing custody credentials.
5. Use verified hardened-host egress for separately authorized Supabase network restrictions; verify Data API disabled and SSL enforcement, changing each separately only if required.
6. Require fresh explicit authorization for C2 live DDL, clearly synthetic material for C3, and a separate availability/cost decision and authorization for C4 real credentials.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

## Catalog command error privacy (2026-10-01, historical validation)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made during that historical validation. Later bootstrap and live observation passed, as recorded above. The historical pending-policy/access incident is no longer the current boundary.

## OIDC template preflight (2026-10-01, historical validation)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The SCP change and OIDC bootstrap were subsequently completed, and live run #1 succeeded. Those later observations supersede the old browser/session blocker. Offline work itself did not verify live AWS state. The successful live run also reported checkout Node.js deprecation and ubuntu-latest migration notices; these remain nonblocking maintenance follow-ups.

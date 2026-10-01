# Work resume handoff

Updated: 2026-10-02 (Asia/Tokyo).

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

## Completed Tokyo IAM update and first inventory (historical)

The user authorized the exact three-action Tokyo inventory IAM addition and one manual run at 19:20:46 JST on 2026-10-01. The resolved change-set JSON was reviewed at 19:49:27 JST: one Modify of GitHubLightsailReadOnlyRole, Replacement=False, with only the GetInstances/GetStaticIps/GetKeyPairs statement conditioned on ap-northeast-1 added. Before/after contexts preserved trust, role identity and every other property. The user's CloudFormation events screenshot confirmed role UPDATE_COMPLETE at 19:52:35 JST and stack UPDATE_COMPLETE at 19:52:49 JST.

Evidence is the resolved change set, completion events and successful OIDC/inventory calls. A separate post-update IAM policy/trust read-back was not performed; do not claim independent live read-back.

[Inventory run #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36852494617) ran exactly once on main `a713b6d57199975e13c32edd84cee9d2ed2da602` (PR #160 merged). Job `110337191404` succeeded, including OIDC and inventory. Sanitized output time: 2026-10-01 10:59:23 UTC / 19:59:23 JST.

| Observation | Verified result |
| --- | --- |
| Region | ap-northeast-1 |
| Instances / static IPs / key pairs | 0 / 0 / 1 |
| Proposed instance / static-IP name collisions | false / false |
| Default key identity | Unknown; version 1 classifier was defective |
| Key login / independent account identity / stack-name inventory | Not verified |
| Live creation authorized | false |

### Default-key classification defect and correction

Version 1 matched `LightsailDefaultKey-ap-northeast-1`, a download filename stem, instead of the documented API default key name `LightsailDefaultKeyPair`. Its `tokyo_default_key_present=false` and `TOKYO_DEFAULT_KEY_NOT_OBSERVED` therefore do not establish default-key absence. The 0/0/1 counts remain valid. Key names were intentionally not exported, so the single key cannot be identified retrospectively from the log. Do not create or download a key on that evidence.

Version 2 uses the documented API name. Regression fixtures use independent literals, including the downloaded filename stem and a custom key, so a wrong production constant cannot make its own tests pass. All 33 local inventory regression tests passed, using synthetic responses only. PR #161 merged the correction after all five applicable CI workflows passed; the separately authorized version 2 live verification is recorded above.

At the end of the first run, the original one-run authorization was consumed and corrected live revalidation remained pending. The user subsequently authorized exactly one additional run at 20:37:39 JST; its successful result is recorded above. Paid host/IP provisioning remains separately unapproved.

AWS documents the name in [keyPairName output](https://docs.aws.amazon.com/cli/latest/reference/lightsail/get-instance-access-details.html). This is a documentation reference only; GetInstanceAccessDetails was not called or granted.

## Verified catalog facts (historical, before creation)

| Item | Observed result |
| --- | --- |
| Region | `ap-northeast-1` available |
| Availability zones | `ap-northeast-1a`, `ap-northeast-1c`, `ap-northeast-1d` |
| Active Ubuntu LTS blueprints | `ubuntu_24_04` (24.04 LTS), `ubuntu_22_04` (22.04 LTS) |
| Matching bundle | `micro_3_0`, Micro, Linux/Unix |
| CPU / RAM / disk | 2 vCPU / 1 GiB / 40 GiB |
| Monthly transfer | 2048 GiB |
| Bundle price | USD 7/month |
| Included public IPv4 | 1 |
| Static IPv4 allocation | Not tested; read-only observation forbids `AllocateStaticIp` |
| Live creation authorization | `false` |

AWS public documentation rechecked on 2026-10-01 states that a static IPv4 attached to a Lightsail instance has no additional charge; an address left unattached for more than one hour costs USD 0.005/hour. Source: [AWS billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html). This is a published pricing rule, not proof that this account can allocate an address.

## Next action and authorization boundary

1. Creation, native SSH and read-only H1 are complete. Use `SECRET_CUSTODY_HOST_H1_EVIDENCE.md`; do not recreate or re-run setup without a changed condition.
2. H2a installation and H2b live verification are complete. Finish exact-head CI for bounded H2c synthetic memory verification and use the existing Termius session once; preserve the fixed inactive installation and all gates.
3. Confirm complete relevant current firewall rules before H3/H4; preserve the bounded phone/browser administration path. The manual /32 source differs from the original browser-only template.
4. Qualify effective sandbox/resource limits, no-secret capacity, default-deny egress, verified static egress, TLS verify-full and reboot/recovery before introducing custody credentials.
5. Use verified hardened-host egress for separately authorized Supabase network restrictions; verify Data API disabled and SSL enforcement, changing each separately only if required.
6. Require fresh explicit authorization for C2 live DDL, clearly synthetic material for C3, and a separate availability/cost decision and authorization for C4 real credentials.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## Completed AWS bootstrap and root cause

- The user removed the AWS mobile app; Safari subsequently reached Proof of Concept IAM. Earlier browser/app/session hypotheses are historical, not the current blocker.
- Proof of Concept Tokyo CloudFormation returned an explicit SCP deny. The Root-attached `AdvancedModeRegionRestrictionSecurityControlPolicy` had a `RegionFloor` deny whose exception list omitted Tokyo.
- Management-account CloudShell ran read-only `prep.sh` and `review.sh`: `READ-ONLY PREP COMPLETE`, then `REVIEW PASS`.
- Review preserved all non-RegionFloor statements and the original Effect/NotAction/Resource. It retained the original region exceptions globally and added Tokyo only for Proof of Concept. Proposed compact SCP size: 5814 / 10240 characters.
- The user explicitly approved the reviewed policy change. `apply_scp.sh` checked live drift, applied that proposal, read it back and reported `SCP UPDATE VERIFIED`; a rollback copy remained in that CloudShell session.
- Proof of Concept Tokyo CloudFormation then loaded without the SCP error.
- Reviewed stack `keirin-ai-github-oidc-readonly` created exactly `GitHubActionsOidcProvider` and `GitHubLightsailReadOnlyRole`; both reached `CREATE_COMPLETE`.
- The user registered its output as Actions secret `AWS_READONLY_ROLE_ARN`; GitHub confirmed `Repository secret added.`.
- The subsequent successful OIDC workflow independently confirms the read-only role can be assumed. Do not repeat SCP update, stack creation or secret registration.

## Work browser authentication findings

The Work browser initially had no GitHub session. GitHub reported that this account does not support password sign-in. The user selected Google; Google device approval and GitHub emailed device verification then completed, and the authenticated workflow page allowed dispatch. Do not retry unsupported GitHub password sign-in. Browser session persistence is not guaranteed; inspect actual state if UI access is needed again. Do not store credentials, codes, account identifiers or session URLs in the repository. Prefer GitHub connector tools for supported reads/writes; UI was needed only because workflow dispatch was not exposed by the connector.

## Fixed safety state

The runtime and custody restrictions remain unchanged; resource creation and H1 have progressed as recorded above:

- hosted task/provider execution OFF;
- production prediction OFF;
- prediction DB writes OFF;
- automatic external race-data fetching OFF;
- provider generation/write unbound;
- scheduler/recurrence OFF;
- report delivery OFF;
- no real provider/OAuth refresh credential connected or held in custody;
- no C2 live secret-store DDL applied;
- one paid candidate and attached static IPv4 exist; H1 passed, full hardening is pending.

The original catalog workflow made its three catalog reads. The later inventory workflow made the three authorized Tokyo inventory reads after short-lived OIDC authentication. The user separately completed the reviewed IAM update. Neither workflow allocated an IP, created a host/key, downloaded key material, or changed IAM/SCP or Supabase.

## Offline validation and remaining maintenance

PR #152's catalog script suppresses raw AWS CLI stderr and stops on command failure. Its 58 synthetic tests and PR #153's `cfn-lint==1.57.1` validation are historical offline evidence, separate from the successful live run above. Do not copy raw authentication logs into repository evidence; they may contain non-secret but account-specific role identifiers.

The successful run reported an actions/checkout@v4 Node.js 20 deprecation warning and an ubuntu-latest migration notice. These did not fail the run and are maintenance follow-ups, not justification for repeating live observation.

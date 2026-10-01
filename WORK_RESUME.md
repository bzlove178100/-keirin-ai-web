# Work resume handoff

Updated: 2026-10-01 (Asia/Tokyo).

## Current boundary: corrected Tokyo inventory complete; default key observed

Read this section first when the user says `続けて`. The SCP, OIDC bootstrap and initial catalog observation are complete; do not restart phone-console setup, recreate the stack/secret, or rerun the observation without a new reason.

- Repository: `bzlove178100/-keirin-ai-web`.
- Catalog run's historical main: `f08bfbb3ed59478653f9055757b138e7c0141dcf` (PR #157 merged).
- PR #157 head `e21f161075908fac10e938a56c11ab6440640cc5` passed all five applicable CI workflows.
- Live workflow: [aws lightsail read-only observation #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36842907590).
- The workflow was dispatched exactly once from main on 2026-10-01, completed successfully, and emitted the sanitized catalog result at 09:28:26 UTC / 18:28:26 JST.
- Job `observe` (`110305976403`): OIDC credential configuration and catalog observation both succeeded.
- This validates the deployed OIDC path and the three catalog reads at that time, not resource creation permission or host readiness.

## Corrected inventory verified on 2026-10-01

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

## Verified catalog facts

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

The Tokyo inventory IAM update and both separately authorized inventory runs are complete. The corrected classifier observed the existing Tokyo default key. Do not request the completed IAM update again, repeat phone-console setup, or rerun inventory as setup.

The follow-up prepared `review/aws_lightsail_candidate.json` and expanded `SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md`. The proposal pins Ubuntu 24.04 LTS / micro_3_0 and exactly one attached static IPv4. It requests only TCP 22 from the lightsail-connect source alias, with no launch script or runtime. Default acknowledgement rejects creation; the privately supplied expected account must match and the region must be Tokyo. Both resources use Retain; execution must preserve successful resources on failure, with an explicit subsequent cleanup decision if needed.

Local cfn-lint 1.57.1 completed with no findings and all 10 candidate safety-contract tests passed. The offline CI now repeats both checks. This is offline preparation, not an AWS change set or live validation.

Default-key identity and absent instance/static-IP name collisions are verified at the corrected inventory time. Next, independently verify account identity, stack-name collision and current price/IDs before a concrete provisioning change-set review. Key login and provisioning permissions remain separate checks. The deployed role can perform the three Tokyo inventory reads and three original catalog reads, but cannot provision resources. Work GitHub authentication is not AWS authentication. If access is unavailable, report that precise blocker rather than repeat completed mobile/bootstrap steps.

Prepare and inspect a CREATE change set with exactly two Add actions, then obtain specific approval of the actual change set, cost, SSH and failure-retention behavior before execution. Resolve current main and follow `AGENTS.md`. Passing observation, lint, CI or an acknowledgement string does not grant live authorization.

A later explicit live-provision authorization must identify exactly one Tokyo candidate, its selected observed Ubuntu LTS blueprint, the USD 7/month bundle ceiling and one attached static IPv4. Do not substitute region/size or create multiple paid hosts. Unknown, unavailable, ambiguous or over-budget values remain a hard stop.

After authorized creation, the host is untrusted/no-secret. Run only read-only/no-secret H1 preflight first. Host hardening, verified static egress, Supabase network restrictions, Data API/SSL management changes, C2 DDL, synthetic C3 custody and C4 real credentials are subsequent separate boundaries. Real always-on custody also needs the reviewed availability/cost decision.

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

All remain unchanged:

- hosted task/provider execution OFF;
- production prediction OFF;
- prediction DB writes OFF;
- automatic external race-data fetching OFF;
- provider generation/write unbound;
- scheduler/recurrence OFF;
- report delivery OFF;
- no real provider/OAuth refresh credential connected or held in custody;
- no C2 live secret-store DDL applied;
- no paid hardened host or static IPv4 provisioned by this work.

The original catalog workflow made its three catalog reads. The later inventory workflow made the three authorized Tokyo inventory reads after short-lived OIDC authentication. The user separately completed the reviewed IAM update. Neither workflow allocated an IP, created a host/key, downloaded key material, or changed IAM/SCP or Supabase.

## Offline validation and remaining maintenance

PR #152's catalog script suppresses raw AWS CLI stderr and stops on command failure. Its 58 synthetic tests and PR #153's `cfn-lint==1.57.1` validation are historical offline evidence, separate from the successful live run above. Do not copy raw authentication logs into repository evidence; they may contain non-secret but account-specific role identifiers.

The successful run reported an actions/checkout@v4 Node.js 20 deprecation warning and an ubuntu-latest migration notice. These did not fail the run and are maintenance follow-ups, not justification for repeating live observation.

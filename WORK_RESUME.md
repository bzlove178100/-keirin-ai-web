# Work resume handoff

Updated: 2026-10-01 (Asia/Tokyo).

## Current boundary: read-only inventory IAM proposal prepared; approval pending

Read this section first when the user says `続けて`. The SCP, OIDC bootstrap and initial catalog observation are complete; do not restart phone-console setup, recreate the stack/secret, or rerun the observation without a new reason.

- Repository: `bzlove178100/-keirin-ai-web`.
- Observed main: `f08bfbb3ed59478653f9055757b138e7c0141dcf` (PR #157 merged).
- PR #157 head `e21f161075908fac10e938a56c11ab6440640cc5` passed all five applicable CI workflows.
- Live workflow: [aws lightsail read-only observation #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36842907590).
- The workflow was dispatched exactly once from main on 2026-10-01, completed successfully, and emitted the sanitized catalog result at 09:28:26 UTC / 18:28:26 JST.
- Job `observe` (`110305976403`): OIDC credential configuration and catalog observation both succeeded.
- This validates the deployed OIDC path and the three catalog reads at that time, not resource creation permission or host readiness.

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

The latest continuation prepared `AWS_LIGHTSAIL_INVENTORY_REVIEW.md`, `review/aws_lightsail_inventory_role_update.yaml`, a bounded/sanitized inventory script and a manual-only workflow. This is an alternative to repeated phone inventory checks. It adds only GetInstances/GetStaticIps/GetKeyPairs in Tokyo to the existing role, pending explicit approval and a matching existing-stack UPDATE change set. It preserves the original OIDC template and all trust/identity parameters. No live IAM update or inventory dispatch has occurred. The current deployed permission remains the three catalog reads.

No SSH-key screenshot or new key evidence was received after the request to inspect Lightsail keys. Do not infer completion from `続けて`. Do not repeat Work's failed AWS browser or CloudShell paths. Next, present the concrete three-read-action update and one inventory run for authorization; after authorization, guide one existing-stack update and verify its exact difference before the run. That is an IAM permission change, not paid host creation. An authenticated AWS console action is still needed for this one-time update; the role cannot update itself.

The follow-up prepared `review/aws_lightsail_candidate.json` and expanded `SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md`. The proposal pins Ubuntu 24.04 LTS / micro_3_0 and exactly one attached static IPv4. It requests only TCP 22 from the lightsail-connect source alias, with no launch script or runtime. Default acknowledgement rejects creation; the privately supplied expected account must match and the region must be Tokyo. Both resources use Retain; execution must preserve successful resources on failure, with an explicit subsequent cleanup decision if needed.

Local cfn-lint 1.57.1 completed with no findings and all 10 candidate safety-contract tests passed. The offline CI now repeats both checks. This is offline preparation, not an AWS change set or live validation.

Next, verify intended account, absent resource names, an existing Tokyo Lightsail key pair (metadata only), and current price/IDs. The deployed OIDC role cannot perform that inventory or provision resources; the separate inventory update above is not yet approved/applied and grants no provisioning permission. Work GitHub authentication is not AWS authentication. No AWS session, existing key, collision check, live change set or provisioning permission has been verified by this preparation. If access is unavailable, report that precise blocker rather than repeat completed mobile/bootstrap steps.

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

The successful workflow made only the reviewed three Lightsail catalog reads after short-lived OIDC authentication. It did not query account-specific static IP resources, allocate an IP, create a host, change IAM/SCP, or change Supabase.

## Offline validation and remaining maintenance

PR #152's catalog script suppresses raw AWS CLI stderr and stops on command failure. Its 58 synthetic tests and PR #153's `cfn-lint==1.57.1` validation are historical offline evidence, separate from the successful live run above. Do not copy raw authentication logs into repository evidence; they may contain non-secret but account-specific role identifiers.

The successful run reported an actions/checkout@v4 Node.js 20 deprecation warning and an ubuntu-latest migration notice. These did not fail the run and are maintenance follow-ups, not justification for repeating live observation.

# Work resume handoff

## Latest live AWS state: SCP root cause and reviewed proposal

This section supersedes the earlier unresolved browser/app/session diagnosis for the immediate AWS bootstrap boundary.

Verified from the user's live AWS console and CloudShell session on 2026-10-01:

- The AWS Console mobile app was removed. After returning through Safari, the Proof of Concept session could open IAM in-browser.
- In Proof of Concept IAM, the dashboard showed 0 identity providers. A search for role `keirin-ai-github-lightsail-readonly` returned no match. Treat these as observations from that account/session, not organization-wide absence.
- Tokyo `ap-northeast-1` was added to the console's visible-region settings and then appeared in the region selector.
- CloudFormation in Proof of Concept, Tokyo, failed `ListStacks` with an explicit deny from `AdvancedModeRegionRestrictionSecurityControlPolicy`.
- The exact SCP referenced by the error was inspected in the management account. It is attached to Root.
- The `RegionFloor` statement is `Effect: Deny` and its `StringNotEquals/aws:RequestedRegion` list contains exactly `eu-north-1`, `unspecified`, `us-east-1`, and `us-west-2`; Tokyo is not present.
- Management-account CloudShell in `ap-southeast-2` eventually opened successfully after an initial session-timeout attempt.
- `prep.sh` was uploaded and run. It performed read-only Organizations calls, wrote `current_scp.json` and `proposed_scp.json`, and reported `READ-ONLY PREP COMPLETE`. It did not change AWS.
- `review.sh` was uploaded and run. It reported `REVIEW PASS`, confirmed that all non-RegionFloor statements are unchanged, `Effect / NotAction / Resource` are unchanged, the global RegionFloor keeps the existing region list while excluding only the Proof of Concept account from that statement, and a second `RegionFloorProofOfConcept` statement allows exactly the current regions plus `ap-northeast-1` for Proof of Concept. Proposed compact SCP size was 5814 / 10240 characters.
- The user explicitly approved the reviewed change. `apply_scp.sh` was uploaded and run in the management-account CloudShell. It re-read the live SCP, verified there was no drift from `prep.sh`, applied exactly `proposed_scp.json`, read the policy back, and reported `SCP UPDATE VERIFIED`. A local rollback copy was saved as `current_scp_before_update.json` in that CloudShell session.

Immediate next verification boundary:

- The reviewed SCP update has been applied and read-back verified. Do not run `organizations update-policy` again unless a new reviewed change is required.
- CloudFormation `ListStacks` in Proof of Concept Tokyo was then re-tested and succeeded: the stack list loaded with no SCP error and showed 0 stacks.
- Next, return to the Proof of Concept session and verify that CloudFormation `ListStacks` succeeds in Tokyo `ap-northeast-1`.
- If Tokyo CloudFormation still fails, stop and diagnose the new concrete error; do not repeat the SCP update.
- Tokyo CloudFormation access was verified.
- The reviewed CloudFormation stack `keirin-ai-github-oidc-readonly` was created through a reviewed change set containing exactly two additions: `GitHubActionsOidcProvider` and `GitHubLightsailReadOnlyRole`. Both reached `CREATE_COMPLETE`.
- The stack output `ReadOnlyRoleArn` was copied by the user and registered in GitHub as the repository Actions secret `AWS_READONLY_ROLE_ARN`; GitHub displayed `Repository secret added.`
- The next step is to run the manual `aws lightsail read-only observation` workflow and verify the sanitized Tokyo catalog output. Do not recreate the stack or secret.
- The OIDC bootstrap is now live enough for the next read-only GitHub Actions observation. Hand off the next substantial execution/verification to Work. Work should read this file first, then use GitHub rather than restarting phone-console AWS steps. A Work cloud browser session does not inherit the user's Safari session, but GitHub repository state is the shared handoff.


Updated: 2026-10-01 (Asia/Tokyo)

Use this file when resuming in ChatGPT Work.

## Resume command

If the user says only `続けて` in Work, read the latest incident state below and the troubleshooting protocol in `AGENTS.md` before proposing an operation. Resume without redoing completed work or repeating failed instructions under unchanged conditions.

## Latest incident state: AWS browser/app/session loop

The user requested a stop to ad-hoc instructions and repeated manual work. Live AWS navigation and creation are paused pending evidence-based diagnosis. This is the current immediate boundary; the later OIDC bootstrap sequence below is not an instruction to restart it now.

Evidence from user-provided screens on 2026-10-01 (screen times are not independently verified AWS timestamps):

- A CloudFormation `ListStacks` error explicitly referred to `us-east-1` and an SCP deny. It does not establish a deny in Tokyo.
- A later CloudFormation screen displayed no red error and 0 stacks with the active-status filter. Account and region were not visible. This is not evidence of no stacks in all accounts/regions, no IAM provider/role, or stack-creation authorization.
- Browser console home and service search were reached. The user reports that selecting IAM opened the AWS mobile app sign-in screen.
- Entering the suggested generic IAM URL subsequently showed `Choose AWS sessions`, with Proof of Concept listed as signed in 11 minutes earlier. The screen itself showed no authentication error.
- Regional policy completion remains user-reported, as recorded in PR #155. Do not ask for SCP editing again without new relevant evidence.

Unresolved: the browser/app routing and account/session transition mechanism, the exact authentication method, effective target-account/Tokyo permissions, existing OIDC provider/role, stack creation, role-ARN registration and live observation. Do not label an 8-hour session timeout, IAM Identity Center, universal links or a cookie fault as the established cause from these screens alone.

Already attempted without a stable verified IAM path: generic console/IAM URLs, repeated account selection/sign-in guidance, browser address-bar paste guidance and service-search navigation. Do not start this sequence over. AWS app deletion was only suggested; execution and outcome were not reported. It is not the default next action or a verified fix. No private screenshot, account ID, session URL, role ARN or personal identifier is stored here.

Before any further user action, state the remaining diagnostic question, the evidence supporting the hypothesis, what has changed since the failed attempt, the least-invasive distinguishing check, its success criterion and its stop condition. Use existing evidence and available read-only tools first. Ask for only the missing information that changes the next decision, not another screenshot of an already understood screen. Do not dispatch a live workflow as an access probe.

A verified browser route to IAM and the intended CloudFormation account/region must be established before returning to the duplicate check and reviewed change set. Distinguish route recovery from IAM/SCP authorization and from live stack creation. A workaround is not a proven root-cause fix.

## Verified repository state

- Repository: `bzlove178100/-keirin-ai-web`
- Verified base for this incident/protocol update: `d77ed768e8d0ed33327437b2156115541f491516` (PR #155 merged).
- PR #151 (GitHub OIDC read-only observation) is merged.
- PR #149 exact-head CI passed: collection progress UI regression, agent runtime read-only smoke, keirin-ai regression, and agent checkpoint PostgreSQL contract all succeeded.
- Resolve the current `main` from GitHub when resuming; do not treat an embedded SHA as permanently current.
- AWS account bootstrap is recorded as complete: Proof of Concept account available, paid usage enabled, advanced features activated, and USD 10 AWS Budget configured with Credit/Refund excluded.
- No Lightsail instance or static IP provisioning has been verified.
- Public CloudShell in Tokyo failed with an environment/permission error; do not keep retrying CloudShell or create a CloudShell VPC environment.
- The planned observation path is GitHub Actions OIDC with short-lived read-only AWS credentials, after the unresolved access/bootstrap boundary.

## Fixed safety state

Keep all of these unchanged unless the user separately authorizes the specific live boundary:

- hosted task/provider execution OFF;
- production prediction OFF;
- prediction DB writes OFF;
- automatic external race-data fetching OFF;
- provider generation/write unbound;
- scheduler/recurrence OFF;
- report delivery OFF;
- no real provider/OAuth refresh credential connected;
- no real refresh secret stored in custody;
- no C2 live secret-store DDL applied;
- no paid hardened host provisioned.

## Subsequent bootstrap after access diagnosis

Read `AWS_GITHUB_OIDC_READONLY_OBSERVATION.md` together with the latest incident state above.

Do not resume screenshot-by-screenshot AWS console navigation and do not retry public CloudShell or repeat the regional SCP phone-editing flow.

### Policy and bootstrap state (2026-10-01)

- The Work Cloud Browser returned `Site Unavailable` for AWS. The cause is not established; do not repeat that browser attempt without a material change. The user's phone session cannot be controlled through that browser.
- The user later confirmed that the regional SCP/policy step is complete. Treat that step as completed unless AWS returns a new, concrete permission failure relevant to the intended operation. This completion is user-reported; it has not been independently read back from AWS by ChatGPT.
- The earlier phone-editor difficulty and `builderid:*` validation finding are historical troubleshooting context only. Do not ask the user to repeat that editing flow or remove existing policy exceptions solely to clear the old finding.
- The OIDC CloudFormation stack, its `ReadOnlyRoleArn` output, the repository secret, and a live observation run remain unverified; unverified is not proof of absence.

After the access boundary is resolved, the next bootstrap is CloudFormation, not Organizations/SCP editing. Before stack creation, check for an existing stack/provider/role in the intended account so a partial prior attempt is not duplicated. Stack execution remains a separate important-operation confirmation after reviewing the concrete change set.

The subsequent bounded bootstrap is:

1. create the reviewed `review/aws_github_oidc_readonly_role.yaml` CloudFormation stack in the Proof of Concept AWS account;
2. copy only its `ReadOnlyRoleArn` output;
3. store that ARN as the GitHub Actions secret `AWS_READONLY_ROLE_ARN`;
4. run the manual `aws lightsail read-only observation` workflow.

Do not create an AWS access key. The workflow uses GitHub OIDC and short-lived credentials.

The workflow must observe only sanitized facts required by `SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json`:

1. selected region is exactly `ap-northeast-1`;
2. an Ubuntu LTS Linux/Unix blueprint is available and its exact blueprint identifier;
3. the candidate bundle is available and matches exactly 2 vCPU / 1 GiB RAM / 40 GiB storage / 2 TB transfer;
4. displayed monthly bundle price is at or below USD 7;
5. static IPv4 availability and displayed pricing/conditions;
6. no automatic region or size substitution is required.

Unknown, ambiguous, unavailable, mismatched, or over-budget values are a hard stop.

## Do not do during observation

- do not create/start/stop/reboot/resize/snapshot/clone/delete an instance;
- do not allocate/attach/detach/release a static IP;
- do not create/change SSH keys;
- do not change firewall/network/DNS/load balancer/database/container/storage settings;
- do not change IAM/account/billing/support settings;
- do not change Supabase management settings or run C2 DDL;
- do not create/read/write Vault/provider credentials;
- do not enable hosted execution, prediction writes, race-data fetching, scheduling, or reporting.

## After successful observation

Report the observed sanitized values to the user and stop. Passing observation is **not** creation authorization. Ask for a separate explicit live-provision authorization before creating one Lightsail candidate and one static IPv4.

If authorized later, continue with exactly one candidate, then read-only/no-secret H1 preflight before any host mutation. Any live hardening, Supabase network restriction, Data API/SSL management change, C2 DDL, synthetic C3 credential, or C4 real credential activation remains a separate authorization boundary.

## Catalog command error privacy (2026-10-01, historical validation)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made during that validation. It verified no OIDC stack, role secret or live observation. The later user-reported SCP completion and current access incident above supersede the former pending-policy note; failed Cloud Browser/CloudShell retries remain paused.

## OIDC template preflight (2026-10-01, historical validation)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The regional SCP/policy step is treated as complete based on the user's later confirmation. Do not repeat failed phone editing instructions. Resume from the latest access incident, not the old pending-policy or create-stack instruction. No stack, role secret, or live observation has yet been verified.

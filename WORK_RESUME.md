# Work resume handoff

Updated: 2026-10-01 (Asia/Tokyo)

Use this file when resuming in ChatGPT Work.

## Resume command

If the user says only `続けて` in Work, resume from this exact boundary without redoing prior repository review work.

## Verified repository state

- Repository: `bzlove178100/-keirin-ai-web`
- Verified base before this offline observation update: `b03ee168390ef2d98e432cbae80638d11572875c`.
- PR #151 (GitHub OIDC read-only observation) is merged.
- PR #149 exact-head CI passed: collection progress UI regression, agent runtime read-only smoke, keirin-ai regression, and agent checkpoint PostgreSQL contract all succeeded.
- Resolve the current `main` from GitHub when resuming; do not treat an embedded SHA as permanently current.
- AWS account bootstrap is complete: Proof of Concept account available, paid usage enabled, advanced features activated, and USD 10 AWS Budget configured with Credit/Refund excluded.
- No Lightsail instance or static IP has been provisioned.
- Public CloudShell in Tokyo failed with an environment/permission error; do not keep retrying CloudShell or create a CloudShell VPC environment.
- The next observation path is GitHub Actions OIDC with short-lived read-only AWS credentials.

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

## Immediate next action in Work

Read `AWS_GITHUB_OIDC_READONLY_OBSERVATION.md` first.

Do not resume screenshot-by-screenshot AWS console navigation and do not retry public CloudShell or repeat the regional SCP phone-editing flow.

### Current bootstrap state (2026-10-01)

- The Work Cloud Browser returned `Site Unavailable` for AWS. The cause is not established; do not repeat that browser attempt. The user's phone session cannot be controlled through that browser.
- The user later confirmed that the regional SCP/policy step is complete. Treat that step as completed unless AWS returns a new, concrete permission failure that directly contradicts it. This completion is user-reported; it has not been independently read back from AWS by ChatGPT.
- The earlier phone-editor difficulty and `builderid:*` validation finding are historical troubleshooting context only. Do not ask the user to repeat that editing flow or remove existing policy exceptions solely to clear the old finding.
- The OIDC CloudFormation stack, its `ReadOnlyRoleArn` output, the repository secret, and a live observation run remain unverified.

The next live action is CloudFormation, not Organizations/SCP editing. Before stack creation, check for an existing stack/provider/role so a partial prior attempt is not duplicated. Stack execution remains a separate important-operation confirmation after reviewing the concrete change set.

The next bounded bootstrap is:

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

## Catalog command error privacy (2026-10-01)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made. OIDC stack creation, role secret setup, the pending SCP save, and live observation remain unverified; Cloud Browser/CloudShell retries remain paused.

## OIDC template preflight (2026-10-01)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The regional SCP/policy step is now treated as complete based on the user's later confirmation. Do not repeat the blocked browser/CloudShell attempts or failed phone editing instructions. The next live dependency is creating the reviewed OIDC CloudFormation stack in the Proof of Concept account. No stack, role secret, or live observation has yet been verified.

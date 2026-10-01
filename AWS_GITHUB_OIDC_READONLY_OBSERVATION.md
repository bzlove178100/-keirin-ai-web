# AWS GitHub OIDC read-only observation

Reviewed: 2026-10-01 (Asia/Tokyo)

## Goal

Stop repeated manual AWS console navigation. After one bounded bootstrap, GitHub Actions can inspect the Lightsail Tokyo catalog using short-lived OIDC credentials.

This path is **read-only**. It does not create a Lightsail instance, static IP, key pair, firewall rule, VPC, credential, database object or provider binding.

## Current live boundary

The AWS account bootstrap has completed outside this repository:

- the user completed the AWS account/Paid Plan setup;
- advanced AWS features were activated;
- a USD 10 monthly AWS Budget was created for monitoring;
- Credit and Refund are excluded from that budget's charge-type filter;
- no Lightsail host has been authorized or provisioned;
- public CloudShell launch in Tokyo failed, so CloudShell is no longer the required path.

Do not place account IDs, card data, addresses, phone numbers, IAM credentials or screenshots containing personal data in this repository.

## One-time bootstrap

Use the **Proof of Concept** AWS account, not the organization management/delegated-admin accounts.

1. Open AWS CloudFormation in the Proof of Concept account.
2. Create a stack from `review/aws_github_oidc_readonly_role.yaml`.
3. Review the change set before creation. The stack is limited to:
   - one GitHub OIDC identity provider;
   - one IAM role;
   - one inline policy with only:
     - `lightsail:GetRegions`
     - `lightsail:GetBlueprints`
     - `lightsail:GetBundles`
4. After the stack succeeds, copy the `ReadOnlyRoleArn` output.
5. In GitHub repository settings, create the Actions secret `AWS_READONLY_ROLE_ARN` with that ARN.
6. Run the workflow **aws lightsail read-only observation** manually.

The workflow uses GitHub OIDC and short-lived AWS credentials. Do not create an AWS access key for this path.

Before executing the stack, check for an existing GitHub OIDC provider, role or stack so a partial prior attempt is not duplicated. Prefer uploading the reviewed YAML file rather than retyping its contents. Review the actual change set and obtain the separate stack-execution confirmation before creating IAM resources. A prepared template is not proof of an AWS-validated or deployed stack.

The current browser, regional SCP and phone-editor blockers are recorded in `WORK_RESUME.md`. Region activation alone does not prove SCP authorization. Keep account-specific policy drafts private and verify their actual saved state before live observation; do not remove existing policy exceptions or disable organizational controls to clear editor findings.

## Trust boundary

The trust policy is restricted to the immutable GitHub OIDC subject for:

- owner: `bzlove178100`;
- owner numeric ID: `320407427`;
- repository: `-keirin-ai-web`;
- repository numeric ID: `1357382962`;
- branch: `main`;
- audience: `sts.amazonaws.com`.

If GitHub changes the emitted subject or the repository/owner identity changes, fail closed and review the trust policy before changing it.

## Automated observation

`review/aws_lightsail_readonly_observation.sh` performs only three AWS service calls:

- `lightsail:GetRegions`;
- `lightsail:GetBlueprints`;
- `lightsail:GetBundles`.

It rejects any region other than Tokyo `ap-northeast-1` before an AWS call. It fails unless the catalog returns Tokyo, at least one explicitly active Ubuntu Linux/Unix OS blueprint with a nonempty identifier and explicit LTS text, and an explicitly active, identifiable bundle matching:

- 2 vCPU;
- 1 GiB RAM;
- 40 GiB disk;
- 2048 GiB monthly transfer;
- Linux/Unix support;
- exactly one included public IPv4 address;
- a finite nonnegative numeric price no greater than USD 7/month.

Missing activity state, malformed numeric values (including booleans, numeric strings and NaN), or absent LTS evidence are not success. An entry with incomplete facts cannot become a candidate. No alternative region/size is selected. API errors stop execution without retry or a success report.

Run `python3 -m pytest -q tests/test_aws_oidc_readonly_observation.py` for the offline synthetic contract. The test substitutes a local AWS CLI stub and does not use AWS credentials. Passing it does not validate AWS IAM/SCP policy, establish actual blueprint availability, or authorize provisioning.

Field references: [Blueprint](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_Blueprint.html) and [Bundle](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_Bundle.html).

The output deliberately omits account identity and does not query existing static IP resources, because those results can disclose account-specific network identifiers.

## Static IPv4 boundary

Static IPv4 allocation is **not** probed automatically because proving allocation availability would require a mutating `AllocateStaticIp` call.

The reviewed public AWS documentation remains the source for the pricing rule: attached Lightsail static IPv4 addresses have no additional charge, while a static IPv4 left unattached for more than one hour is billed at USD 0.005/hour.

Live allocation remains part of a later explicit provisioning authorization only.

## Non-authorization

Passing the read-only workflow does not authorize:

- creating an instance or static IP;
- creating IAM access keys;
- widening IAM permissions;
- host hardening mutations;
- Supabase management changes or C2 DDL;
- secret/provider credential creation;
- hosted execution, scheduler, report delivery, production prediction, prediction DB writes or external race-data fetching.

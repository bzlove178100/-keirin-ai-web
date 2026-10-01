# Tokyo Lightsail read-only inventory review and evidence

Updated 2026-10-01. Status: IAM update and both separately authorized inventory runs completed; version 2 observed the existing Tokyo default key. This document is evidence, not execution authority.

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


## Original proposal: reason and alternatives (historical)

Catalog run 36842907590 succeeded with the existing GitHub OIDC role, but that role grants only GetRegions, GetBlueprints and GetBundles. It cannot check existing instances, static IPs or key pairs. No SSH-key screenshot or other new key evidence has been received. Work's AWS browser previously returned Site Unavailable, and the available plugin search found no AWS control-plane plugin. Do not repeat that failed browser path, CloudShell launch or bootstrap without changed evidence.

The smaller-permission alternative is to inspect these items in the user's existing authenticated AWS console. To reduce repeated phone checks, this separate proposal permits automated Tokyo inventory through the already working OIDC connection. A user decision is needed before the live IAM update; no permission has been widened in AWS by this preparation.

## Exact permission delta

Use `review/aws_lightsail_inventory_role_update.yaml` only as an UPDATE proposal for the existing `keirin-ai-github-oidc-readonly` stack. It preserves the original provider, role identity, parameters, trust policy, tags, outputs and three catalog actions from `review/aws_github_oidc_readonly_role.yaml`. The only added statement is:

| Action | Purpose |
| --- | --- |
| lightsail:GetInstances | Count Tokyo instances and detect the proposed instance-name collision |
| lightsail:GetStaticIps | Count Tokyo static IPs and detect the proposed IP-name collision |
| lightsail:GetKeyPairs | Read Tokyo key metadata, including the default key's presence |

The added statement requires `aws:RequestedRegion=ap-northeast-1`. These list/read APIs have no resource-level restriction in the service authorization table, so Resource is `*`; the grant can read all three resource categories in Tokyo, not only the proposed names. The script's output filter is not an IAM restriction on what the role can read.

It adds no instance/IP/key creation, deletion, attachment, port change, SSH access, DownloadDefaultKeyPair, GetInstanceAccessDetails, CloudFormation deployment or IAM-management permission. No access key, OIDC provider, role or GitHub secret is to be newly created. The original catalog template remains unchanged as the reviewed baseline; applying it later to remove the inventory statement is a separate reviewed IAM update, not an automatic rollback.

## Original approved execution procedure (completed; do not repeat)

The original approval request was limited to this three-action Tokyo read-only IAM delta and one subsequent manual inventory run. It does not include the paid host proposal or any key creation.

The original procedure was:

1. In the authenticated Proof of Concept account, Tokyo CloudFormation, select the existing `keirin-ai-github-oidc-readonly` stack. Do not create another stack or re-register AWS_READONLY_ROLE_ARN.
2. Use Update stack / replace current template with the reviewed inventory-update template from the exact approved Git commit. Preserve every existing parameter value, role name and stack setting. First compare the live template/policy with the original baseline; unexpected drift is a stop, not permission to overwrite.
3. Create and inspect an UPDATE change set. The only acceptable resource change is Modify of GitHubLightsailReadOnlyRole with Replacement=False, adding exactly the inventory statement. No provider change, Add/Remove, trust change, parameter change, replacement or additional policy is covered. The named-IAM acknowledgement is needed because this updates an IAM role.
4. Execute only if the actual change set matches the authorized scope. A matching change set does not require repeating the same approval; any new difference does. Verify UPDATE_COMPLETE and read back the role's inline policy and unchanged trust. If AWS denies the operation, stop and diagnose the specific returned action; do not alter SCP or add broader permissions.
5. Run `aws lightsail read-only inventory` from main exactly once, setting its approval checkbox only after the authorized IAM update is verified. Keep the existing role-ARN secret. Do not dispatch as a permission probe before approval/update.

The user completed the one-time stack update in their authenticated AWS console. The connected GitHub role still cannot update its own permissions; this does not establish a Work AWS browser session.

## Inventory behavior and privacy

`review/aws_lightsail_readonly_inventory.py` calls only GetInstances, GetStaticIps and GetKeyPairs after the workflow's short-lived OIDC authentication. GetKeyPairs explicitly includes the default key pair and never downloads a key. The manual-only workflow is main-only, defaults its approval input to false and masks the AWS account ID in the credential action. The checkbox is an operational interlock, not evidence of user consent.

The CLI projects each resource to name, region and type plus pagination token. Those values remain in the short-lived process; no inventory artifact or raw response is uploaded. Public Actions output contains only the timestamp, fixed region, resource counts, collision booleans, Tokyo default-key presence and fixed review reasons. It omits IPs, ARNs, account ID, key names/fingerprints/material, tags and raw AWS errors. As with other workflows, do not commit raw credential-action logs to repository evidence.

Pagination is explicit and limited to 20 pages per operation, with a 120-second total inventory deadline. Inventory CLI retries are disabled. The credential action is separate from that inventory-call limit. A timeout, denial, malformed/duplicate resource, repeated token or unfinished pagination reports incomplete inventory without partial counts or an absence conclusion. Errors expose only the fixed operation, allowlisted reason and numeric exit status; they cannot distinguish IAM from SCP without a separately scoped private diagnosis.

Even successful inventory is not a creation-ready result:

- Existing instances or static IPs require review before another resource is created; resources elsewhere are not inventoried.
- A missing default key is reported, not generated. Custom-key names are not exported or automatically selected. Key metadata is not proof of browser SSH login.
- Account identity is not independently verified; the existing role secret must still belong to the intended account.
- CloudFormation stack-name collisions, current pricing, allocation availability and provisioning permissions are not checked.
- `authorized_for_live_create` is always false. No host, static IP or paid service is created, and all runtime/provider/prediction gates remain disabled.

The single-host CloudFormation proposal and actual CREATE change-set review remain the subsequent, separately authorized boundary.

## Offline validation

Run `cfn-lint -r ap-northeast-1 -t review/aws_lightsail_inventory_role_update.yaml` and `python -m pytest -q tests/test_aws_lightsail_readonly_inventory.py`. Tests use synthetic responses only and cover later-page collisions, complete empty lists, missing default keys, denied/partial replies, redaction, timeouts, pagination/region boundaries, the exact IAM delta and manual workflow gating. No successful offline check means that the AWS update or live inventory happened.

## Official references

- [Lightsail service authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lightsail.html)
- [Requested-region condition](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-requestedregion)
- [GetInstances](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_GetInstances.html)
- [GetStaticIps](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_GetStaticIps.html)
- [GetKeyPairs](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_GetKeyPairs.html)

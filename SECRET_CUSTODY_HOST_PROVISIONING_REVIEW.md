# Secret-custody host provisioning review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — no AWS resource creation is authorized by this file**

This review converts the selected Amazon Lightsail Tokyo 1 GB candidate into an exact provisioning contract that can be checked immediately before a separately authorized live create. It does not create an instance, static IP, SSH key, IAM identity, firewall rule, DNS record or billing commitment.

## Verified cost boundary

Immediately before this review was prepared, current AWS documentation still listed the Linux/Unix Micro 1 GB bundle with public IPv4 at USD 7/month maximum, 2 vCPU, 1 GB RAM, 40 GB SSD and 2 TB transfer. AWS documentation also states that a Lightsail static IPv4 has no additional charge while attached to an instance; an unattached static IPv4 can incur hourly cost.

The first live candidate must therefore remain:

- one Linux/Unix Micro 1 GB instance;
- Asia Pacific (Tokyo), `ap-northeast-1`;
- public IPv4 capable so a Lightsail static IPv4 can be attached;
- maximum reviewed bundle price USD 7/month;
- exactly one attached static IPv4;
- no load balancer, managed database, block-storage add-on or second instance.

If the control plane no longer offers this shape in Tokyo or the price has changed materially, stop before creation and re-review. Do not silently select a more expensive bundle.

## P0 — account and region guard

Before a live create, verify in the authenticated AWS control plane:

- the intended AWS account is selected;
- the Lightsail region is Tokyo / `ap-northeast-1`;
- no existing resource with the intended custody-host name would be overwritten or confused with the candidate;
- the exact 1 GB public-IPv4 bundle is available;
- the current displayed maximum monthly price is at or below the reviewed USD 7 boundary unless the user explicitly authorizes a new price.

Do not create or rotate IAM access keys for this task. Prefer the already authenticated console/session boundary used for the one-time provisioning action.

## P1 — instance shape

The candidate starts with no application secret and no provider capability.

Required creation properties:

- one Linux/Unix instance only;
- Ubuntu LTS family preferred for the first candidate because the existing host qualification assumes systemd, cgroup v2 and nftables-compatible Linux tooling;
- exact current blueprint ID/version must be read from the live Lightsail control plane at creation time and recorded privately in qualification evidence;
- 1 GB / 2 vCPU / 40 GB / 2 TB bundle contract;
- Tokyo zone selected by Lightsail within the Tokyo region; do not move to another AWS region to obtain capacity without a new review;
- no launch script that contains a password, token, provider credential, Supabase key or repository secret;
- no automatic hosted-worker start on boot;
- no production prediction or keirin data-fetch activation.

A default image may be used only as the starting point for no-secret qualification. It is not trusted until H1-H7 hardening/qualification passes.

## P2 — static IPv4

Immediately after instance creation, allocate one Lightsail static IPv4 and attach it to the candidate.

Rules:

- do not leave the static IPv4 unattached beyond the bounded provisioning window;
- do not commit the address to this public repository;
- do not place the address into the Supabase network allowlist until host egress behavior has been verified from the hardened host;
- if the instance is destroyed, either reattach the address promptly to the approved replacement path or release it after evidence/rollback review;
- never use the instance's dynamic public IPv4 as the long-term custody-project allowlist identity.

## P3 — initial ingress

The initial Lightsail firewall is a bootstrap boundary only.

Before any secret exists:

- public HTTP/HTTPS is unnecessary and must not be relied upon;
- no agent/runtime port may be exposed publicly;
- SSH, if used, must be temporary and restricted to the narrowest administratively usable source once the source is known;
- IPv4 and IPv6 ingress are reviewed independently;
- the host-side firewall remains a separate required control and is not replaced by the Lightsail firewall.

Do not guess the user's current home/mobile IP and commit it as an allowlist. Administrative source addresses are private operational data.

## P4 — no-secret first boot

The first boot and all H1 host preflight work are explicitly no-secret.

The host must not receive:

- custody database password;
- Supabase service-role key;
- Vault secret material;
- provider OAuth access/refresh tokens;
- GitHub PAT or repository write token;
- production race/prediction payloads;
- hosted task activation instructions.

The existing `review/lightsail_host_preflight.sh` may be copied to the host through the reviewed administration channel and run read-only. Its sanitized result, not raw operational identifiers, may later be committed as evidence.

## P5 — fail-closed outcome

A created candidate remains disposable until qualification completes.

Destroy the instance promptly if any of these is true and cannot be corrected without weakening the contract:

- memory pressure/OOM makes the 1 GB candidate unsuitable;
- required systemd/cgroup-v2/nftables primitives are unavailable;
- default-deny egress cannot be represented safely;
- stable static egress cannot be proven;
- verify-full TLS to the custody database cannot be qualified;
- reboot/recovery does not preserve the intended fail-closed state;
- logging/platform behavior exposes secret-bearing data once synthetic secret tests begin.

Do not upgrade to the USD 12 bundle automatically. A size change is a new cost decision supported by the failed 1 GB qualification evidence.

## Provisioning manifest

`review/lightsail_provisioning_manifest.template.json` is the repository-side contract for this boundary. It deliberately contains no AWS account ID, IP address, key, hostname, secret or live resource identifier. Live values must remain in private operational evidence.

The manifest's `authorized_for_live_create` field stays `false` in Git. A live action is authorized only by a fresh user instruction in the execution context; repository state alone never grants authorization.

## Current tool boundary

GitHub OIDC catalog observation succeeded on 2026-10-01. The deployed role permits only GetRegions, GetBlueprints and GetBundles; it cannot create resources or inspect existing instances/key pairs. `AWS_LIGHTSAIL_INVENTORY_REVIEW.md` separately proposes three Tokyo inventory reads, pending authorization and an existing-stack update; it grants no provisioning permission. Actual provisioning still requires an authenticated AWS-capable control-plane session with the separately reviewed scope. Work GitHub login is not an AWS session.

## Non-authorization

This review does not authorize or perform AWS provisioning, charges, IAM/SSH-key creation, firewall mutation, Supabase management-plane changes, C2 DDL, database-password creation, Vault/binding creation, provider credential use, hosted execution, scheduling, report delivery, production prediction, prediction DB writes or external race-data fetching.

## Concrete CloudFormation proposal after live catalog observation

Prepared 2026-10-01 after successful read-only run [36842907590](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36842907590).

`review/aws_lightsail_candidate.json` is a locally reviewable CloudFormation proposal, not a deployed stack. Its exact desired resources are:

| Logical resource | Proposed configuration |
| --- | --- |
| CustodyCandidate | One Ubuntu 24.04 LTS `ubuntu_24_04`, `micro_3_0`, in one observed Tokyo zone |
| CustodyStaticIp | One static IPv4, explicitly attached to that candidate after its creation |

The observed bundle is 2 vCPU / 1 GiB / 40 GiB / 2048 GiB transfer at USD 7/month. The template pins the observed IDs but cannot enforce future AWS prices; the live P0 price check remains mandatory. Taxes, exchange conversion, transfer overage and separately approved extras are not a guaranteed all-in USD 7 bill. The initial planned resource names are `keirin-custody-h1` and `keirin-custody-h1-ip`; these are proposed names, not existing resources.

The default acknowledgement is NOT_AUTHORIZED. Template rules require an explicit acknowledgement, Tokyo, and a privately supplied expected account matching the deployment account. An acknowledgement string is an execution interlock, not proof of user consent or an IAM access control. Keep the Git manifest's `authorized_for_live_create=false`.

An existing Tokyo Lightsail key-pair name is required with no default. Verify it by metadata only before execution; do not retrieve a private key. This avoids silently depending on an unverified default key. If no usable key exists, stop and review the separate key-creation boundary; do not create an access key or SSH key as a fallback.

The requested platform firewall is TCP 22 only, using AWS's `lightsail-connect` source alias with empty explicit IPv4 and IPv6 CIDR lists. No HTTP, HTTPS or runtime port is requested. This is a temporary administration proposal requiring approval together with the instance creation. It does not prove live firewall state, disable IPv6 on the host, or implement host-side outbound restrictions. CloudFormation operations must not be assumed atomic; inspect the actual IPv4/IPv6 rules before H1 and before treating the host as safe.

### Execution sequence after approval

1. Use the intended Proof of Concept account's authenticated AWS control plane, in Tokyo. The existing GitHub OIDC role cannot deploy this template. Its separate Tokyo inventory-read proposal requires its own authorization; do not add provisioning permissions, a provisioning workflow or IAM access keys.
2. Verify account, region, the proposed stack/instance/static-IP names are absent, the required existing key pair is available, and the selected blueprint/bundle/price remain correct. Any denied or incomplete inventory leaves the result unknown and stops creation.
3. Upload the template for a CREATE change set; leave OnStackFailure unset so DisableRollback can be selected at execution. Privately supply ExpectedAccountId and the verified ExistingKeyPairName, and inspect the resolved parameters. Use one zone from the observed set; no automatic capacity fallback.
4. The change set must contain exactly two Add actions: CustodyCandidate (AWS::Lightsail::Instance) and CustodyStaticIp (AWS::Lightsail::StaticIp). No modify/remove/import/nested stack/IAM/key/add-on action is acceptable. Review any service-managed key or service-role side effect instead of treating it as implicitly authorized.
5. Obtain explicit approval of the actual change set, cost and bootstrap SSH rule before Execute. Offline lint/tests are not AWS validation or live authorization. Do not create from an unresolved login session or use workflow dispatch as a permission probe.
6. At execution, use the preserve-successful-resources / disable-rollback option (`DisableRollback=true`), not automatic delete or rollback. Keep RetainExceptOnCreate=false; do not combine DisableRollback with a previously supplied OnStackFailure. Verify these options in the live execution surface. If they cannot be selected or confirmed, stop.
7. After execution, verify the instance is running with exact blueprint/bundle/region and the sole static IP is attached to it. Read back the actual platform port rules for both IP families. No second host/IP or automatic re-execution is allowed on timeout or uncertain response; inventory first.
8. If all checks pass, continue only to read-only/no-secret H1 using the reviewed script and browser SSH. Any missing tooling, failed capacity or listener check blocks qualification; do not install packages or alter the host during H1.

### Retention and failure handling

Both resources explicitly use DeletionPolicy=Retain and UpdateReplacePolicy=Retain. This prevents stack removal from being treated as an authorized resource cleanup; it also means retained resources can continue costing money. DisableRollback must be confirmed separately at execution. Neither retention nor a timeout is permission to leave resources unattended.

On partial creation or failed IP attachment: stop, inventory once, record the private resource state, and seek a narrowly scoped attach/release/delete decision for only the candidate resources. A static IP left unattached beyond one hour can incur the published USD 0.005/hour charge. Do not blindly retry the CREATE change set, create a replacement or trigger stack rollback/delete. If the user later authorizes cleanup, verify both the instance and static IP are actually removed; deleting only the CloudFormation stack is insufficient with Retain.

No launch script, runtime activation, real provider credential, account ID or IP is embedded in the template. Outputs include only the no-secret qualification label and region. Private live account/key/resource details remain outside Git.

### Validation and limits

Run `cfn-lint -r ap-northeast-1 -t review/aws_lightsail_candidate.json` and `python -m pytest -q tests/test_aws_lightsail_candidate_template.py`. These are offline schema and safety-contract checks only. The live account inventory, current price, key existence, AWS change-set validation, permissions, firewall read-back, attachment and host qualification are still unverified.

Official references:

- [ExecuteChangeSet failure options](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_ExecuteChangeSet.html)
- [Lightsail instance resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lightsail-instance.html)
- [Port and lightsail-connect alias](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-lightsail-instance-port.html)
- [Static IP attachment](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lightsail-staticip.html)
- [Lightsail billing](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html)

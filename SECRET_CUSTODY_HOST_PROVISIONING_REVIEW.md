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

The connected tools in this chat can maintain the repository and inspect public provider documentation, but no AWS account control-plane action is currently connected. Therefore this review can be completed and tested here, while actual Lightsail creation requires an authenticated AWS-capable browser/tool session.

## Non-authorization

This review does not authorize or perform AWS provisioning, charges, IAM/SSH-key creation, firewall mutation, Supabase management-plane changes, C2 DDL, database-password creation, Vault/binding creation, provider credential use, hosted execution, scheduling, report delivery, production prediction, prediction DB writes or external race-data fetching.

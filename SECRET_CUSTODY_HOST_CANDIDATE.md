# Secret-custody hardened-host candidate

Reviewed: 2026-10-01 (Asia/Tokyo)
Status: **candidate selected for later qualification — no host provisioned and no cost incurred**

## Decision

Use **Amazon Lightsail, Asia Pacific (Tokyo), Linux/Unix Micro 1 GB with public IPv4** as the first hardened-host candidate for C2/C3 qualification.

Current published bundle shape:

- region: Asia Pacific (Tokyo) / `ap-northeast-1`;
- 2 vCPU;
- 1 GB RAM;
- 40 GB SSD;
- 2 TB transfer allowance;
- USD 7/month maximum bundle price;
- attached Lightsail static IPv4: no additional charge.

This is a qualification candidate, not an authorization to create the instance. No AWS account is assumed to exist or be available. Account creation is now a separate explicit authorization boundary defined in `AWS_ACCOUNT_BOOTSTRAP_BOUNDARY.md`. No AWS account, instance, static IP, SSH key, IAM credential, database credential, network rule, secret, provider credential or billing commitment is created by this review.

## Why this is the lowest-cost candidate that currently preserves operational margin

The project requirement is not absolute minimum headline price; it is minimum cost **without creating an avoidable operational problem**.

Options checked against current official documentation:

| Option | Current headline cost | Region / IP shape | Decision |
|---|---:|---|---|
| DigitalOcean Basic 512 MiB | USD 4/month | Singapore is the nearest listed region; leased public IPv4, reserved IP available | Do not use as the primary candidate: 512 MiB has too little qualification margin and the database is in Tokyo. |
| Lightsail Nano 0.5 GB | USD 5/month | Tokyo; static IPv4 can be attached at no extra charge | Do not use as the primary candidate: 0.5 GB leaves the same memory-margin concern. |
| **Lightsail Micro 1 GB** | **USD 7/month** | **Tokyo; attached static IPv4 included** | **First qualification candidate.** |
| Hetzner CPX12 | USD 17.99/month after the 2026-06 adjustment | Singapore | Higher current cost and cross-region. |
| GitHub larger runner with static IP | metered runner cost plus qualifying GitHub plan | static IP requires GitHub Enterprise Cloud | Not the lowest-cost route for this project. |

The USD 7 Lightsail candidate is therefore the lowest verified option in this review that combines Tokyo placement, a re-assignable static IPv4 boundary, and 1 GB rather than 512 MiB of memory.

If live synthetic qualification shows memory pressure, OOM termination, unacceptable restart behavior, or insufficient hardening headroom, do **not** weaken safeguards to fit the USD 7 bundle. Move to the next reviewed size instead. The current Lightsail 2 GB public-IPv4 bundle is USD 12/month.

## Source boundary

Pricing and capability statements above were re-checked against current provider documentation on 2026-10-01:

- Amazon Lightsail instance bundles / pricing;
- Amazon Lightsail regions and availability zones;
- Amazon Lightsail static IP and billing documentation;
- Amazon Lightsail firewall documentation;
- DigitalOcean Droplet pricing, regional availability and Reserved IP documentation;
- Hetzner 15 June 2026 cloud price adjustment;
- GitHub larger-runner and Actions runner pricing documentation;
- Railway pricing, deployment-region and Static Outbound IP documentation;
- Render pricing, region and dedicated outbound IP documentation.

The 2026-10-01 re-check did not identify an alternative that improves the current Tokyo + static-egress + low-fixed-cost boundary. Re-check the provider control plane immediately before provisioning because prices and product limits can change.

## Static egress requirement

The Supabase custody-project database/pooler network restriction must use the actual hardened-host egress address, not a guessed address and not the user's phone/home/mobile network.

For the Lightsail candidate:

1. create the instance only after explicit provisioning authorization;
2. attach one Lightsail static IPv4 before treating the host identity as stable;
3. record the static IPv4 privately and use its `/32` only after outbound-source behavior is directly verified from the host;
4. never publish the real allowlist address in this public repository;
5. if the host is replaced, reassign the static IP and re-run TLS/network qualification before resuming credential work.

The default dynamic public IPv4 is not acceptable as the long-term Supabase allowlist identity because it can change after stop/start.

## Host firewall / egress boundary

Lightsail's platform firewall controls inbound traffic and allows outbound traffic. Therefore the platform firewall alone does **not** satisfy the existing exclusive-egress security contract.

Before any custody DB credential or Vault material is introduced, the host must additionally enforce outbound policy at the operating-system layer. The intended boundary is:

- default-deny outbound at the host firewall;
- allow only the exact DNS/NTP/update/bootstrap destinations required during a bounded bootstrap phase;
- after bootstrap, allow only the minimum runtime destinations, including the reviewed Supabase database/pooler endpoint and explicitly required GitHub/runtime control endpoints;
- no provider network access until a separately authorized provider capability is bound;
- log metadata only, never secret payloads or connection strings;
- fail closed if the destination set cannot be represented safely.

The exact destination set must be generated from the deployed runtime contract and qualified with the existing synthetic network/logging guards before C3.

## Inbound boundary

Base Lightsail images can start with permissive inbound rules. The custody host must not remain in that state.

Before qualification:

- remove public HTTP/HTTPS rules unless a reviewed service actually requires them;
- do not expose the custody runtime or database-facing broker as a public service;
- restrict temporary SSH to the minimum approved administrative source during bootstrap, then remove or further constrain it when an alternate recovery path is established;
- treat IPv4 and IPv6 firewall rules separately;
- if IPv6 is not required for the reviewed path, do not leave an unnecessary public IPv6 ingress path enabled.

## Capacity qualification gate

The 1 GB candidate passes cost review only. It still has to pass a live synthetic host qualification before use:

- OS boots and remains healthy after security updates;
- no OOM kill or sustained memory exhaustion under the exact secret-host process composition;
- process deadlines, child reaping and crash recovery remain effective;
- TLS `verify-full` to the custody database succeeds with the approved CA/hostname path;
- static egress IPv4 is observed as expected;
- host egress rules block unapproved destinations;
- approved Supabase network restriction allows the host and rejects a non-approved route;
- log-policy and pgAudit/redaction expectations remain satisfied;
- restart/reboot preserves the intended static-IP and service state;
- no secret/provider material is used for this qualification.

If any one of these fails because of resource pressure, the candidate is rejected rather than relaxing the safety contract.

## Cost-control rule

Do not keep multiple paid hosts running for convenience. The intended progression is:

1. keep all remaining code/review work at zero incremental host cost;
2. when live host qualification is explicitly authorized, create one USD 7/month candidate;
3. qualify it with synthetic/no-secret data;
4. destroy it promptly if rejected, taking advantage of hourly/on-demand billing where applicable;
5. only move to the USD 12/month size if evidence shows the 1 GB candidate is insufficient.

A free/spot/preemptible host is not acceptable for the credential-custody runtime merely because its price is lower if it can be reclaimed or paused unexpectedly.

## Non-authorization

This decision does not authorize:

- creating or charging an AWS resource;
- creating IAM users/keys or distributing an AWS credential;
- changing the Supabase Data API, SSL-enforcement or network-restriction settings;
- applying C2 DDL;
- creating a database password, Vault secret, binding row or provider credential;
- enabling provider refresh/write, hosted task execution, scheduler/recurrence, report delivery, production prediction, prediction DB writes or external race-data fetching.

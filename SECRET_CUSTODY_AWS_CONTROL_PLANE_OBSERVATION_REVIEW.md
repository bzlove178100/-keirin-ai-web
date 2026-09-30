# Secret-custody AWS control-plane observation review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — observation does not authorize AWS resource creation or mutation**

This review prepares the exact evidence to collect from an authenticated AWS Lightsail control-plane session before any paid host is created. It does not perform the observation and does not contain live AWS account, instance, network, key, or credential data.

## Purpose

The next live AWS session must answer only the questions required to decide whether the already-reviewed host candidate is still available and still fits the approved cost/safety envelope.

Required observations are limited to:

- selected region is exactly `ap-northeast-1`;
- an Ubuntu LTS Linux/Unix blueprint suitable for the reviewed host is available, with the exact control-plane blueprint identifier recorded in the session evidence;
- the selected bundle displayed by AWS matches 2 vCPU, 1 GiB memory, 40 GiB storage and 2 TB transfer;
- the displayed monthly bundle price does not exceed USD 7;
- a static IPv4 can be allocated/attached under the reviewed pricing assumptions;
- no automatic size substitution or region substitution is required.

An observation result that differs from any required host shape or price boundary is a **stop**, not permission to silently choose a different resource.

## Read-only boundary

The observation session must not:

- create, start, stop, reboot, resize, snapshot, clone or delete an instance;
- allocate, attach, detach or release a static IP;
- create or change SSH keys;
- change Lightsail networking/firewall rules;
- create DNS, load balancers, disks, databases, containers or other billable resources;
- change account, IAM, billing, budget, region-default or support settings;
- call Supabase or modify any database/Vault/provider/prediction/race-data state.

`review/lightsail_control_plane_observation.template.json` therefore keeps `authorized_for_live_create=false` and all live observation values unset.

## Sensitive-data handling

Do not commit or paste into repository evidence:

- AWS account IDs, organization IDs or billing identifiers;
- access keys, secret keys, session tokens, cookies or authorization headers;
- private SSH keys or key material;
- live instance names/IDs;
- public/private instance IPs or static IP addresses;
- source allowlist addresses or administrative CIDRs;
- private hostnames;
- database connection strings or credentials.

Public catalog-like values needed to identify the chosen blueprint/bundle may be recorded in a sanitized operational observation after the authenticated session, but the repository template itself stays unset.

## Decision rule

The observation is acceptable only when all required values are directly observed in the authenticated control plane and match the reviewed candidate. Unknown, unavailable, ambiguous or conflicting values fail closed.

Passing this observation still does **not** authorize creation. Instance/static-IP creation requires a separate explicit live-provision instruction after the observed values and displayed cost have been reviewed.

## Evidence template

The template separates expected values from observed values. Expected values are repository-reviewed constraints. Observed values are initialized to `null`/`unknown` and are not guessed.

The offline validator requires:

- observation-only status;
- live-create authorization false;
- exact reviewed region and maximum monthly price boundary;
- no automatic region/size substitution;
- every observation value initially unset;
- every runtime/provider/prediction gate false;
- no credential/account/IP/key fields or executable AWS mutation commands.

## Exit criteria

After an authenticated AWS session, continue only if the sanitized observation shows an exact match and the user separately authorizes live provisioning. If the observation does not match, remain at this boundary and review a new candidate without weakening security controls.

## Non-authorization

This review does not authorize or perform AWS provisioning, instance/static-IP changes, firewall/network changes, key management, host hardening, Supabase management changes, C2 DDL, Vault/binding creation, credential use, provider actions, hosted execution, scheduling, report delivery, production prediction, prediction DB writes or external race-data fetching.

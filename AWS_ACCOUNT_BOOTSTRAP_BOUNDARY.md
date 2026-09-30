# AWS account bootstrap boundary

Reviewed: 2026-10-01 (Asia/Tokyo)
Status: **review complete — no AWS account creation or AWS resource creation authorized**

## Account availability state

Do not assume that an existing AWS account is available.

At this boundary, AWS account availability is unconfirmed and the workflow must behave as though no usable AWS account exists until the user explicitly establishes or confirms one.

Do not repeatedly request an AWS login or treat a failed Work browser session as evidence that an account exists.

## Provider re-check

The hardened-host provider was re-checked before introducing an account-creation step.

The first qualification candidate remains **Amazon Lightsail, Asia Pacific (Tokyo), Linux/Unix Micro 1 GB with public IPv4** because current public provider documentation still gives the required combination of:

- Tokyo deployment region `ap-northeast-1`;
- 2 vCPU;
- 1 GB RAM;
- 40 GB SSD;
- 2 TB transfer;
- USD 7/month public-IPv4 bundle pricing;
- a static IPv4 path suitable for the later exact-egress allowlist design.

Alternatives do not currently improve this boundary:

- Railway's documented deploy regions include Southeast Asia (Singapore), not Tokyo; its Static Outbound IP feature requires the Pro plan.
- Render's documented Asia region is Singapore, not Tokyo; dedicated outbound IP sets require a Pro workspace and a separate high monthly IP-set charge.
- DigitalOcean's current region list includes Singapore and Sydney but no Tokyo.

This is a provider-selection review only. It does not authorize account signup or spend.

## Account-creation authorization boundary

Creating an AWS account is a separate explicit authorization boundary because signup can require billing information, identity/contact information, verification steps and acceptance of AWS terms.

Before account creation:

1. explain the expected host cost separately from account signup;
2. obtain explicit user authorization to create an AWS account;
3. require the user to enter passwords, payment-card details, phone/identity verification and other sensitive signup data directly into AWS;
4. never ask the user to paste passwords, full card data, one-time codes or recovery secrets into ChatGPT;
5. do not create IAM users, access keys, API keys or programmatic credentials as part of signup.

Creating an AWS account does **not** authorize creating any Lightsail instance, static IP or other billable resource.

## After account creation

After an account is established, the next AWS action remains observation-only:

1. open Lightsail;
2. select/confirm Tokyo `ap-northeast-1`;
3. observe Ubuntu LTS blueprint availability and exact identifier;
4. observe the Micro 1 GB bundle shape and displayed monthly price;
5. observe static IPv4 availability and displayed conditions;
6. make no resource changes.

Unknown, ambiguous, unavailable, mismatched or over-budget values fail closed.

Passing observation still requires a separate explicit live-provision authorization before creating one candidate instance and one static IPv4.

## Non-authorization

This review does not authorize:

- AWS account creation;
- payment-method registration on the user's behalf;
- Lightsail instance/static-IP creation;
- IAM/access-key creation;
- host hardening mutations;
- Supabase management-plane changes;
- C2 DDL;
- secret/provider credential creation;
- hosted execution, scheduler/recurrence, reporting, production prediction, prediction DB writes or external race-data fetching.

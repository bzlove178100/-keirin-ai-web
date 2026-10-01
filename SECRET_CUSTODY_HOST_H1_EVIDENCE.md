# Lightsail creation and H1 evidence

Observed: 2026-10-01 (Asia/Tokyo).
Status: **one candidate created; H1 passed; untrusted / no-secret; H2-H7 pending**.

## Evidence and limits

This is a sanitized record of the user's phone-console and Termius screenshots reviewed in the working conversation. Work did not independently log into AWS or the host. Account identifiers, public/private IPs, source allowlists, host fingerprints, private-key material and original screenshots are intentionally excluded.

- The approved single-candidate CloudFormation stack reached CREATE_COMPLETE at 21:25:39 JST. The static-IP resource completed at 21:25:38 JST. The console subsequently showed the instance running and a static IP attached. This completes the existing creation operation; do not create a second candidate or repeat its approval.
- Initial platform ingress was displayed as Lightsail browser SSH only. Browser SSH reached the Ubuntu prompt, but the user could not reliably enter/execute commands from the iPhone browser. Earlier pasted preflight text is not execution evidence.
- The user completed a bounded administration change: the observed mobile public IPv4 as one /32 source for TCP 22, retaining Lightsail browser SSH IPv4 access. The edit form closed after Update rule. A separate complete post-save firewall read-back was not captured; successful later SSH is connectivity evidence, not full IPv4/IPv6 rule verification.
- The user downloaded/imported the existing Tokyo default SSH key into Termius on the phone. Sync Keys & Identities was observed OFF. No private key was sent to Work or committed. Import alone did not bind the key to the host.
- A later log showed successful SSH handshake and a known/matching host key, followed by public-key authentication failure. After the host's Credentials key selection step, the Ubuntu prompt appeared at 23:15 JST. The last failed stage was authentication, not a network timeout. An independent AWS-versus-Termius host-fingerprint comparison was not performed.
- At 23:20 JST, the user ran echo READY and received READY followed by a new prompt. This verifies command entry and execution through Termius.
- At 23:23 JST, the screenshot showed the reviewed hash-checking loader, the full H1 output, RESULT PREFLIGHT_OK_NO_MUTATION and a returned prompt.

The H1 script came from immutable commit `2322e4cca4d0aebb3d34ed5f1b02969339b72292`, path `review/lightsail_host_preflight.sh`, blob `1210f29d9dd9cf0a3af6dce963480d420ccc673b`. The loader checked SHA-256 `4a2bdf3d965deb8cf7be43c8cc5aee8e81b34f4f6539b906b753ed04c2dbcf7b` before execution. The script was also fetched from that commit and inspected by Work. The loader fetched public code from GitHub; the H1 script itself performs read-only local checks.

## Sanitized H1 result

| Check | Observed result |
| --- | --- |
| Linux / Ubuntu 24.04 / systemd | PASS |
| Required commands, including nft and ss | PASS |
| cgroup v2 | PASS |
| Existing reviewed 1 GB-class memory floor | PASS |
| Swap disabled | PASS |
| No unexpected wildcard TCP listener except bootstrap SSH | PASS |
| Root read visibility | PASS |
| Warning count / failure count | 0 / 0 |
| Final result | PREFLIGHT_OK_NO_MUTATION |

The script compares usable MemTotal with 900000 kB; passing does not assert that Linux reports a full 1 GiB usable memory or that the eventual workload has sufficient headroom. The script reports core-pattern/controller facts but does not prove effective service core-dump suppression, all sandbox controls, UDP exposure or the complete firewall policy.

## Current operational boundary

The candidate is still **untrusted / no-secret**. H1 is complete, not full host qualification. No hardening package, package update, host firewall mutation, reboot/recovery qualification, runtime installation/activation or custody/provider secret introduction is established by this result.

The restricted phone administration source is a manual deviation from the initial browser-only CloudFormation template. Review that difference before any future stack update; do not silently overwrite it or widen ingress. Native SSH can fail later if the mobile source changes; only a new network failure warrants rechecking that source.

Do not repeat browser keyboard workarounds, key import, creation, inventory or H1 without a concrete new reason. The earlier EOF during host-key confirmation had an unconfirmed timeout hypothesis; do not promote it to a proven root cause. The observed successful Termius login is the verified workaround for the browser input problem.

## Next work

1. Prepare the concrete H2 administrator/filesystem/service-boundary change and rollback from the existing declarative hardening and recovery plans, offline first. Define exact changes, prerequisites, verification and failure behavior before requesting live-apply approval.
2. Do not treat the H1 result or original creation approval as live hardening approval. The repository's apply/recovery authorization flags remain false.
3. Before H3/H4 application, obtain the complete relevant current firewall state, preserve the working recovery/admin path and review both IP families. Exact runtime destinations and a safe default-deny egress policy remain unresolved.
4. Static egress, TLS verify-full, effective sandbox/resource limits, reboot/recovery and capacity qualification remain H2-H7 work.
5. Supabase management changes, C2 DDL, synthetic C3, C4 real credentials and paid availability each retain their separate gates. Hosted execution, production prediction, prediction DB writes, external race-data fetching, scheduler and report delivery remain OFF.

No additional user screenshot or command is required merely to re-prove this completed H1 run.

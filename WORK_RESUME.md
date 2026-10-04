# Work resume handoff

Updated: 2026-10-03 (Asia/Tokyo).

## Current boundary: fixed DNS transport through independent recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #184 merged at `99110f436a3cb8ac1bd1b94342d09e0fdbf43144`. Final corrected head `231acd82c86d806480f47b883fed1412cdc47fa1` passed all five workflows and fifteen regression jobs (`37163379851`). Its PMTU job `111321280325` passed ten standalone and sixteen recovery records. H2d job `111321280201` passed fourteen local and five real-systemd tests including intentional collection before stale reset. This continuation rechecked the merge, exact final workflows and matching clean local/remote main. The earlier reset failure remains historical evidence; its omitted state is not retroactively proved by the reproduced race.

This slice adds mandatory `custody-dns-recovery` with installed `dig` and bounded synthetic DNS servers in a private dual-stack network. Require actual A/AAAA answers over UDP, explicit TCP and UDP truncation→TCP fallback under maintenance, after controller SIGKILL with qualification active, and after independent two-table restoration. A silent approved server must cause a bounded failed query; an unapproved changed endpoint must remain denied over UDP/TCP; re-enabling the original server with changed data must yield fresh answers. Actual unsolicited replies from the approved address must reach netdev then be denied by inet conntrack, and wrong-source replies must be denied at netdev. Existing/new administration, old/new qualification denial, final rule shape and cleanup remain required. Fourteen local DNS/recovery helper tests pass; CI evidence is pending. See [DNS recovery review](SECRET_CUSTODY_DNS_RECOVERY_REVIEW.md). All five final-head workflows and sixteen regression jobs are the integration gate; exact final evidence and merge receipt belong in the PR.

Initial head `2973efc9ff5b19d1dad02148afbf6899ded00519`, regression `37165073764`, DNS job `111326222401`, passed baseline, both maintenance/qualification transport sets, independent restoration and IPv4 post-restoration DNS. It then failed the expected-outage assertion: dig correctly returned exit 9 (no response), but its single-semicolon banner was incorrectly counted as an answer. The parser now excludes both single/double-semicolon diagnostics and requires exactly exit 9 plus no answer lines for negative queries. A regression test rejects arbitrary exit 1, success-without-answer and a failed query containing an answer. Version reporting now checks both stdout/stderr and requires a bounded `DiG ` identity. The changed conditions are result classification/version capture only; no network assertion is skipped. Five DNS and ten helper tests pass (15 total); corrected CI remains required.

This qualifies fixed DNS transport only, not systemd-resolved/NSS, cache or TTL expiry, automatic resolver discovery/failover, DNSSEC, encrypted DNS, or simultaneous DHCP/RA/PMTU lifecycles. No resolver configuration or host clock is changed. Next: synthetic time-source behavior, resolver integration/discovery design and first restricted maintenance installation/recovery design. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and wrong shared allowlists remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: routed PMTU after independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #183 merged at `98f569e29ac7e5b862f5d298704281164ee6121c`. Its final head `1b08ac107d4ad2bfd4e04e478961d0961bbd40d5` passed all five workflows and fifteen regression jobs. Merge state, final workflows and matching clean local/remote main were rechecked on this continuation; all twelve DHCPv6 composition acceptance records remain accepted.

This slice composes routed IPv4/IPv6 PMTU with the existing independent PID 1 recovery worker. Fixed qualification profiles add only the documentation peer's TCP/443 tuple in both owned tables. After controller SIGKILL, actual qualification exchange must succeed; independent atomic restoration must revoke old/new qualification while existing management/bulk and new management connections work. The existing bulk socket must still report PMTU 1500 after restoration. The original forged-error rejection and real router 1500→1280 blocked-PTB stall/same-flow recovery then run under the restored policy. Final shape and old/new denial are checked again. The original standalone fixture stays mandatory. See [PMTU recovery review](SECRET_CUSTODY_PMTU_RECOVERY_REVIEW.md). Code head `ed5e49640688e2384ae95016a170be795b271dd8` passed all sixteen composition acceptance records in regression run `37162795373`, PMTU job `111319533837`, on kernel `6.17.0-1022-azure`. The ten standalone records also passed. For both families the independently restored bulk socket still reported PMTU 1500; subsequent real router errors quoted 1500-byte packets and announced MTU 1280. Blocking them stalled the transfer, and admitting them delivered all 65,536 bytes on the same socket. IPv4 MSS changed 1448→1228, IPv6 1428→1208, with actual unfragmented wire packet lengths at most 1280 and 1280 observed. Post-restoration forged-error rejection, restored shape, old/new qualification denial, management survival and cleanup passed. The composition ended with `SYNTHETIC_PMTU_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 23:46:31 UTC on October 3 (08:46 JST on October 4). Fourteen local tests and `git diff --check` passed. All five code-head workflows succeeded, including all fifteen regression jobs in run `37162795373`. All five final-head workflows are required before integration; final run IDs and merge receipt belong in PR #184.

The first evidence-only head `d56f6fb9c4d21776e94cacafffad3efbb7c81853` passed PMTU again but failed existing H2d job `111320627742` in run `37163162130`. Invalid probe output was correctly rejected as `PROCESS_EVIDENCE_INVALID`; cleanup then replaced that error with `PROCESS_RESET_FAILED`. The log does not contain reset stderr/state, so transient-unit collection between ownership readback and reset is a hypothesis, not a proven diagnosis of that historical run. H2d cleanup now tolerates a nonzero reset only when a new manager readback verifies `LoadState=not-found`; existing directory/cgroup absence checks still run. A retained or unreadable unit still fails. Two local tests cover absent/retained units and remaining cgroups. A real-systemd test forces collection between readback and the actual stale reset, requires its nonzero exit, preserves the original rejection and verifies cleanup. The probe exits nonzero on SIGTERM so the test retains the failed unit until intentional collection. Fourteen H2d local tests pass (28 total with the PMTU/helper checks). Corrected-head CI remains required; no assertion was skipped and no blind rerun was used.

Next: DNS/time protocol lifecycle and first restricted maintenance installation/recovery design. Static routes/neighbors here do not establish simultaneous DHCP/RA/PMTU composition or a route change during the restoration transaction. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and a wrong shared allowlist remain unresolved. Completed phone evidence remains accepted. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 with independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #182 merged at `a8cb390df54b1c183623cfee31d7c905eef8dc39`. Final head `a8fb90bfbec4a575a144952805fe2d0c1d6591b0` passed all five workflows and fifteen regression jobs. GitHub merge and final workflows were rechecked on this continuation; its seventeen dynamic-recovery acceptance records remain accepted.

The next slice adds a fixed DHCPv6 profile to the independent PID 1 worker, using only the previously qualified pinned patched CI networkd build. A real Renew must refresh the lease while the controller is dead and qualification is active; the worker then atomically restores inet and netdev, denying established/new qualification traffic while preserving administration. The original complete lifecycle is reused after restore, with a fresh event window for Renew, alternate-DUID Rebind/adoption and lease expiry while RA routing remains. A post-restore wrong-source frame is rejected. The original-client defect control and standalone patched lifecycle remain mandatory. Seventeen local composition/helper tests plus four builder/provenance tests pass (21 total); all five final-head workflows are required before integration. See [DHCPv6 recovery review](SECRET_CUSTODY_DHCPV6_RECOVERY_REVIEW.md).

Initial PR #183 head `54530d4ce47f13850da3fd8a904bfd9b750fe1fc` failed before compilation in run `37161194778`, job `111314797928`: `PINNED_CLIENT_INPUT_MISMATCH`. All three Ubuntu downloads still match their original hashes. The GitHub-generated fix patch changed only its index abbreviations from 11 to 12 hex digits; restoring the 11-digit representation exactly reproduces original SHA-256 `b581a4c784a89648f8a8f25866a2b66ad57e54e6644a3ab2c8b6fe75fef86ffb`. The current generated patch hashes to `f67ad156f3ec7e005cbdeb7975c5f7af201e2ac081714ea9a6d348d465743667`; the official commit API confirms the same one-line getter fix. The original reviewed bytes are now vendored in `tests/fixtures/dhcpv6-t2-fix.patch`. No pin or source change is accepted automatically: the old SHA check and exact applied one-line comparison remain mandatory. The changed condition is local immutable patch input rather than GitHub's generated representation. Corrected code head `27dd63ef9bc003c04c7e2f62e58da1418bd988a7` then passed the actual composition and all five workflows. Regression run `37161487535` passed all fifteen jobs; DHCPv6 job `111315666049` passed both original/standalone controls and all twelve composition acceptance records, ending in `SYNTHETIC_DHCP6_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY`. The kernel was `6.17.0-1022-azure`. The independent restoration completed at 23:24:42 UTC, fresh post-restoration Renew at 23:24:44, alternate-DUID Rebind/adoption at 23:25:18 and expiry/final denial at 23:26:06. Owned-build cleanup succeeded and the installed networkd SHA-256 was unchanged. Final-head workflow evidence and merge receipt belong in PR #183.

Next is routed IPv4/IPv6 PMTU recovery composition. Installed Ubuntu DHCPv6 remains unqualified. DNS/time lifecycle, worker death after the last readiness check, non-cooperating root writers, reboot, first maintenance installation and a wrong shared allowlist remain unresolved. Completed phone observations stay accepted. No AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: dynamic configuration with independent restricted recovery

Updated: 2026-10-03 (Asia/Tokyo).

PR #181 is merged at `1dd5666d779d82793b63d4a838b023ce1247d7ed`. Final head `f43ecb26969555a49a78a27e2e83ca30c784ce82` passed all five workflows and all fourteen regression jobs; this continuation rechecked the merge and workflow results against GitHub. Its actual IPv4/IPv6 routed PMTU evidence remains accepted.

PR #182 adds mandatory `custody-dynamic-recovery`, which composes installed networkd DHCPv4 and IPv6 RA/SLAAC/ND, in separate private networks, with PID 1 supervised recovery. Both inet and netdev tables are replaced in one nft transaction. The controller dies by SIGKILL; actual renewal/RA refresh must continue during qualification and after restricted restoration, existing/new administration must survive, and old/new qualification connections must fail. Real worker death before apply, controller death before apply, and independent drift in either table are negative cases. Shape comparisons ignore only handles and counter measurements, so legitimate packet counts cannot masquerade as policy drift. See [dynamic recovery review](SECRET_CUSTODY_DYNAMIC_RECOVERY_REVIEW.md). Code head `69ae85206d5bc193de6f538af2df549f959c16d0` passed all five workflows on its first run; regression `37128722659` passed all fifteen jobs. Dynamic recovery job `111219298078` passed all seventeen acceptance records (eight IPv4, nine IPv6) and `SYNTHETIC_DYNAMIC_RECOVERY_OK_NO_LIVE_APPLY`, using kernel `6.17.0-1022-azure` and installed networkd `255.4-1ubuntu8.17`. This success applies to DHCPv4 and RA/ND, not DHCPv6. Actual post-restoration DHCP Renew/Rebind, RA refresh/ND/expiry, worker/controller death cases, both-table drift and cleanup all passed without skipped assertions. Six new local tests and thirteen reused-helper tests also pass. All five final-head workflows must pass before integration; final evidence and merge receipt belong in PR #182.

This slice does not combine DHCPv6 or routed PMTU with recovery yet; these are the next composition targets. Installed Ubuntu DHCPv6 remains unqualified, while the separate pinned patched CI build remains qualified only in its recorded scope. DNS/time lifecycle, worker death after the last readiness check, concurrent non-cooperating root writers, reboot, first maintenance installation and a wrong shared administration allowlist remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host changes or credential use; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: real routed IPv4/IPv6 PMTU fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #180 merged at `c64253ff9443a19b6fa2c0964e9c4a75c0e34d07`. All five workflows for final head `c0affba6344e3a3589e4fe01bef6c3cb16dcb7b9` succeeded, rechecked on this continuation. Its success qualifies only the pinned patched CI build; installed Ubuntu 8.17 DHCPv6 remains unqualified.

PR #181 adds mandatory `custody-routed-pmtu`. Code head `a0e599ec6dde248882980182c7325cc92ec4b9ba`, regression run `37121414940`, job `111198105956`, passed all ten acceptance records and `SYNTHETIC_ROUTED_PMTU_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. Both IPv4/IPv6 real routers emitted valid errors quoting 1500-byte TCP packets and announcing MTU 1280. Blocking those errors stalled the queued transfer; admitting only RELATED PMTU errors recovered the same 65,536-byte transfer. Connected MTU and TCP_INFO PMTU read 1500 then 1280; MSS changed 1448→1228 for IPv4 and 1428→1208 for IPv6. Receiver packet lengths were at most 1280, with a 1280-byte packet observed. Wrong source/code, unrelated quoted flow and out-of-window quoted TCP sequence rejection all passed, including the kernel sequence-rejection counter. TCP/443 stayed denied, existing/new administration remained usable, and namespace/process/link/rule cleanup passed. All fourteen regression jobs and all five code-head workflows succeeded. Four new and three shared-helper local tests pass. See [PMTU review](SECRET_CUSTODY_PMTU_REVIEW.md). All five final-head workflows must pass before integration; final results and merge receipt belong in PR #181.

The first PMTU head `8db90623c103fef7c85cf1bf164e8bb943d24c89` failed router setup in run `37121343744`, job `111197907590`: a missing separator after the nested nft chain produced an explicit parser error. The corrected separator/newline was the changed condition; the next run exercised every required assertion successfully. No PMTU success was claimed from the initial setup failure and no failed assertion was skipped.

This is fixed isolated PMTU qualification, separate from DHCP/RA and rollback. Next compose qualified dynamic controls with independently supervised restricted recovery. DNS/time lifecycle, a fixed live DHCPv6 deployment candidate, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted. No phone/AWS/SSH/live host action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 CI lifecycle

Updated: 2026-10-03 (Asia/Tokyo).

PR #179 merged at `e805038a5c1404c260ab1a63a55726c81ec26810`; its IPv6 RA/ND/DAD evidence remains accepted. PR #180 adds paired real networkd source builds in isolated CI. Code head `e066c8c97f086df0f6cc0900337df2a402583b9b` passed all five workflows. Regression run `37118721668`, DHCPv6 job `111190467251`, built both clients, confirmed the typed defect in the original, and passed all eight patched-client acceptance records plus `SYNTHETIC_DHCP6_LIFECYCLE_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. The patched client acquired its IA_NA address, reported separate timers, refreshed its actual lease, adopted the alternate DUID on the next Renew, preserved administration transport, expired the address while RA routing remained, and cleaned up. All thirteen regression jobs passed. Both root-owned client builds were removed; the installed networkd SHA-256 remained unchanged before and after.

The qualification target is explicitly the minimal custom Ubuntu 255.4-1ubuntu8.17 source build containing official upstream fix `8f5eaeb143dd9e58503980ae5f63dd78c463180e`. Identical build settings and RPATH removal are used for original and patched clients. Four source inputs are SHA-256 pinned; the applied patch is checked as exactly one getter-line change. Internal systemd libraries are statically linked and runtime binaries/manifest verified before use, then bound read-only inside the private client namespace. Twenty-one local tests pass. See [DHCPv6 review](SECRET_CUSTODY_DHCPV6_REVIEW.md) for the source hashes, executable hashes and acceptance evidence. All five final-head workflows must still pass before integration; their results and merge receipt belong in PR #180.

The original installed Ubuntu client remains unqualified: earlier heads `d92e190d82d6e21669a54ff8dc8e8f897137f9a6` and `87cd699cae804a5589764dfd9a9934f6e8bc1fe3` exposed its T2 getter defect. Do not replace this failure with the custom build's success. The first paired build at `a4f032dfc26bcf115e1bb32405a2b7667fb98084` compiled but failed the dependency/search-path gate; identical RPATH removal corrected that build-artifact issue and the next run verified no shared-systemd dependency. No protocol assertion was waived. Historical failures and the changed validation target remain recorded.

Next implement actual constrained-path IPv4/IPv6 PMTU, then compose dynamic control dependencies with independently supervised restricted recovery. Live DHCPv6 still needs an independently reviewed fixed deployment candidate; this CI build is not an installed or vendor-supported remedy. DNS/time lifecycle, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is requested. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: IPv6 RA/ND/DAD control fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #178 merged at `5dd41f9fd28738530b05754582940ef19d08c521`. All five workflows succeeded for final head `89ca803cec06501f4e9b07f18eec4dcdd9266cae`, rechecked on this continuation. Restricted-link DHCPv4 acquisition/renewal/rebinding/expiry and administration survival are complete only in the recorded isolated scope.

The new mandatory IPv6 job reuses the private networkd launcher with a fixed IPv6 profile. It requires actual RA/SLAAC route acquisition/refresh/expiry, dynamic neighbor rediscovery, duplicate-address refusal, header rejection counters and existing/new off-link administration transport. See [IPv6 control review](SECRET_CUSTODY_IPV6_CONTROL_REVIEW.md). Four new local guard/checksum/empty-state tests and five shared DHCP tests pass; actual changed-head CI and all five final-head workflows must pass before integration. Initial head `af9a4a152b53329e2b45b9cb4d74afe0a2113e0f` failed before rule installation because an address-free IPv6 query returned an empty list; the unsafe first-element assumption is corrected with a reproducing local test. No protocol assertion is skipped. Corrected code head `153d681d755c2e332873370eadc01041a55fca42` passed IPv6 job `111179939207` in regression run `37114983663` on kernel `6.17.0-1022-azure`, networkd `255.4-1ubuntu8.17`, with all nine PASS records and `SYNTHETIC_IPV6_RA_ND_DAD_OK_NO_LIVE_APPLY`. Final-head workflow results and merge evidence belong in PR #179.

This is not DHCPv6, PMTU, router/neighbor authentication, complete IPv6 validation or live qualification. Next implement real DHCPv6 lifecycle and constrained-path PMTU, then compose qualified dynamic controls with independently supervised restricted recovery. First maintenance-anchor installation and recovery from a wrong shared allowlist remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is needed. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: DHCPv4 lifecycle composed with restricted link policy

Updated: 2026-10-03 (Asia/Tokyo).

PR #177 merged at `e6f7c597d24c73f0d8f8852631b3c06bd87f67a6`. All five workflows succeeded for its final head `8d3af4b191c246359d3005a7ac773e41d0dda147`, rechecked on this continuation. The protocol-specific versus all-protocol packet-socket distinction and capability-free worker boundary remain accepted.

The next change strengthens the mandatory real networkd DHCPv4 fixture: inet and default-drop netdev restrictions exist before initial acquisition, then remain through unicast renewal, alternate-server rebinding and expiry. It adds pre-rule positive packet controls, exact drop counters for wrong tuples/fragments, qdisc-bypass controls, actual ARP without static neighbors and expired-address reachability refusal. Existing/new TCP administration transport and all prior lifecycle assertions remain required. See [composition review](SECRET_CUSTODY_DHCP_LINK_REVIEW.md). Five DHCP and three packet local tests pass. Code head `d6554eb9184a6ff83c825a015e6ed2f7d7b634bf` passed regression run `37113754710`, DHCP job `111176470089`, with all ten PASS records and `SYNTHETIC_DHCPV4_LINK_POLICY_COMPOSITION_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`, nftables `1.0.9` and networkd `255.4-1ubuntu8.17`. All eleven regression jobs succeeded, including unchanged transition, recovery and packet-boundary jobs. Require all five final-head workflows successful before integration; their results and merge receipt belong in PR #178.

This is a fixed synthetic IPv4 composition, not a live policy, server authentication, ETH_P_ALL capture isolation, address renumbering, ARP spoofing defense or complete maintenance qualification. Next qualify IPv6 control traffic, then dynamic-dependency composition with restricted recovery. The first restricted maintenance anchor and recovery from an incorrect shared allowlist remain unresolved. Completed phone observations remain accepted; no repeated phone/AWS/SSH/host operation is needed. H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: raw packet filtering measured; DHCP link-policy composition next

Updated: 2026-10-03 (Asia/Tokyo).

PR #176 is merged at `d82ed0cf76d3f3bc240b8fba447c081d0465eec9`. Its final head `526dca65c4101a71176e23ceafcb45b8d7ab7bab` passed all five workflows, rechecked on this resumption. The real DHCPv4 lifecycle is complete in its recorded isolated scope. Completed live phone observations remain accepted; do not request identical retries.

PR #177 adds a mandatory CI fixture that measures ordinary UDP, protocol-specific AF_PACKET and ETH_P_ALL receive paths separately. It checks inet versus netdev ingress/egress, normal and qdisc-bypass transmission, wrong tuples/fragments, a separately executed capability-free child and owned cleanup. See [packet boundary review](SECRET_CUSTODY_RAW_PACKET_REVIEW.md). Code head `ce4fa08d8377b4dbf1634231598aa159d6af157c` passed the complete real-kernel job `111173559093` in regression run `37112699408`, including all six PASS records and `SYNTHETIC_RAW_PACKET_BOUNDARY_OK_NO_LIVE_APPLY`, on kernel `6.17.0-1022-azure`. Three local tests passed. The review records the EPERM assertion, direct-egress protocol matching and capability-free checkout-access corrections with their failed and successful evidence. Final-head workflow results and merge receipt are recorded in PR #177; require all five workflows successful before integration.

The design keeps raw capabilities out of the application worker. netdev ingress is not a confidentiality boundary against privileged ETH_P_ALL capture. These are synthetic packet/permission tests, not a live policy or DHCP authentication. Next compose restricted link rules with the actual DHCP lifecycle and existing administration assertions, then IPv6 control packets and fallback. First restricted maintenance installation/recovery remains unresolved. No phone operation or AWS/SSH/host mutation is requested; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: isolated DHCPv4 lifecycle passed; control-packet qualification remains

Updated: 2026-10-03 (Asia/Tokyo).

PR #175 merged at `06646c9b40726517e71da98bcd9509ebc1395b43` after all five workflows succeeded on head `59246821baf89b7bac3a7284e729ba29b52526f1`. The complete user dependency report is accepted below; no identical phone retry is needed.

PR #176 adds `tests/test_secret_custody_network_dhcp.py` and a mandatory Ubuntu CI job. It uses the actual networkd client in private network/mount/runtime/config namespaces and a synthetic DHCP server to test unicast renewal, broadcast rebinding to an alternate server, TCP transport continuity and lease expiry. See [scope and limitations](SECRET_CUSTODY_NETWORK_DHCP_REVIEW.md). Five local parser/namespace/runtime refusal tests pass. The actual lifecycle passed for code head `c7b040e515f72291168ffc42c2ac0bc9d8f9c22f` in regression run `37029254624`, DHCP job `110911645738`, on networkd `255.4-1ubuntu8.17`. Acquisition, unicast renewal with inet counters, alternate-server rebinding with existing/new administration transport, expiry/removal, negative reachability and cleanup all passed. Existing transition and independent recovery jobs also passed.

Resumed PR #176 after the user's pause. Previous head `796f6cf685022501408551008d2c2b1c4092e28a` failed initial acquisition in run `36945051624`, job `110645135668`; all other jobs/workflows passed. Ubuntu's downstream patch uses container detection for link initialization, unlike the upstream read-only-sysfs predicate previously assumed. The correction adds a marker only within verified private runtime storage and a real before/after container-detection check. It keeps isolation and lifecycle deadlines/assertions intact. The corrected real lifecycle now passes; this resolves the CI initialization incident in the measured fixture scope. Final-head workflow results and the merge receipt are recorded in PR #176; require all five workflows green before integration. No phone operation is needed.

Source review identified a material enforcement distinction: DHCP discovery/rebinding use raw packet sockets; bound renewal uses UDP. Only renewal asserts inet firewall counter passage. Passing this fixture must not be described as raw-frame filtering, DHCP authentication, address renumbering or complete maintenance qualification. The existing static transition/watchdog tests remain intact.

Next after this slice: address raw-socket/control-packet enforcement, then DHCPv6/RA/ND/PMTU and composition with fallback. Initial restricted maintenance installation and recovery from a wrong shared allowlist remain unresolved. No live firewall command, independent AWS/SSH access, new resource/IAM/inventory or credential is introduced. H2a and every runtime/provider/prediction/DB-write/data-fetch/scheduler/report gate remain inactive/OFF.

## Accepted live evidence and maintenance design: live dependencies observed; maintenance policy design

Updated: 2026-10-02 08:40 JST (Asia/Tokyo).

PR #174 merged at `1aa360b257da55d91facb857ff16b8be41a63d3e`. Its corrected head `e0ae01e3d92d84e4f127e997cd36bcd9b54a3864` passed all five workflows, rechecked on resumption. Regression run `36904707742` includes successful independent recovery job `110512222225` and local reader job `110512222345`. The earlier CI parser defect is historical and corrected.

The user has now supplied the complete requested dependency evidence: IMG_8937–IMG_8946, terminal captures at 08:17–08:32 JST. The immutable reader finished with `LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION` and returned to the prompt. All selected sections were observed; `mutation=false`, `qualification=false`. This closes the request for that reader output. Do not ask for another identical run or more screenshots of these sections.

Sanitized observations: two interfaces; one DNS endpoint consistent with networkd's DHCPv4 provider data; zero fallback DNS entries; nine Chrony sources, one selected; nine IPv4 and seven IPv6 routes; DHCPv4 address/default-route configuration, DHCPv6 global address configuration, and an RA-derived IPv6 default route. One SSH endpoint tuple is caller-supplied/unverified. These are private user-supplied observations, not an independent Work host session, durable endpoint guarantees or packet-policy qualification. Exact addresses, allowlists and account identifiers stay out of public GitHub.

See [maintenance dependency design](SECRET_CUSTODY_NETWORK_MAINTENANCE_DESIGN.md) for the evidence-to-test matrix and initial-anchor decision. Next repository implementation is an isolated dynamic-address/control-packet fixture: real renewal/rebind, RA/ND and PMTU behavior with negative controls, preserving the existing transition/recovery tests. A UDP echo on DHCP ports does not qualify lease renewal. No live firewall installer or command is ready; the initial restricted maintenance anchor and recovery from a wrong shared allowlist remain unresolved.

H1 and measured H2a/H2b/H2c/H2d are complete. Keep H2a inactive and every runtime/provider/credential/prediction/data-fetch/scheduler/report gate OFF. No extra AWS inventory, IAM change, resource, secret, reboot or live firewall action follows from this evidence. Current unfiltered host state is not an allowed automatic fallback.

## Historical PR #174 preparation: independent recovery rehearsal and private dependency reader

Updated: 2026-10-02 (Asia/Tokyo).

PR #173 is merged at `180e590d1cede88f1326642170b73856d40deeea`. All five workflows passed for head `c321c22f89ec56c3432115993371535b0f9cc1dd`; regression run `36900487170`, job `110498113203`, completed all seven real IPv4/IPv6 transition markers with `SYNTHETIC_NETWORK_TRANSITION_OK_NO_LIVE_APPLY`. The initial fixture failure below was corrected before that successful run. No live firewall changed.

This follow-up implements a PID-1-supervised watchdog rehearsal in disposable network namespaces and a bounded local-only dependency reader. See [review and limits](SECRET_CUSTODY_NETWORK_RECOVERY_REVIEW.md). The real systemd test kills the applying child before/after apply, requires restricted fallback, verifies new/existing administration and qualification traffic in both families, and rejects unknown owned-table drift. Cooperative locks are not protection against arbitrary root writers. Independent recovery, initial anchor, persistence and live concurrency remain unqualified. Require the current PR's actual CI results before claiming this new rehearsal passed.

Initial PR #174 head `0396f275d7e14ef7672e9480284e34841685dd4d` passed the actual independent recovery job `110510991785` (run `36904340074`). The dependency job rejected the real DNS response format. The correction uses explicit D-Bus Properties.Get calls (honoring no-auto-start) and parses the returned variant array correctly, as verified against systemd v255 source. The original private reader is not approved for phone use. Require corrected-head CI; do not skip the failing assertion or ask the user to diagnose this CI-only defect.

The reader selects local interface/address/route/networkd/DNS/Chrony facts without external probes, raw config or credentials. Seven fixed commands are bounded by time/output; unavailable or unsupported sections remain unknown. Default output is counts only; `--private` emits selected private endpoints to the phone terminal. Keep those values out of public GitHub. A report is observation with unresolved items, never a completed policy or apply authorization.

Next: finish exact-head CI and read back the merge; then provide one immutable/hash-checked private reader command for the existing Termius session. This supplies missing dependency evidence, not a repeat of completed H1/H2/nft/UFW probes. Review that new private output before preparing actual profiles and an initial-anchor recovery proposal. Do not invent browser SSH ranges, DNS/NTP/renewal destinations or a recovery path. No live apply artifact exists yet and no firewall approval is requested now.

The user's 02:07–02:16 baseline below remains accepted. H1 and H2a/H2b/H2c/H2d are complete in their measured scopes. H2a remains inactive; all runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Work has no independent AWS/SSH connection. No third inventory run, IAM expansion, new resource, credential entry, production DB action, stress or reboot is authorized by this development step.

## Historical PR #173 preparation: network baseline and isolated transition rehearsal

Updated: 2026-10-02, carrying completed 02:07–02:16 JST evidence (Asia/Tokyo).

PR #172 is merged at `92a4dfed17a385a7045decebb661aa70619b0305`. The user's IMG_8930 at 02:07 shows the corrected observer at `78bbea96eec8d9c8228fe07c4e9ed71dbc1a3e2f`, SHA-256 `92a2f6a135c73d6ed972b61f203ee035e28c5ff7a473934b809041dac8aeb712`, succeeding with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION`. Empty nft objects/base chains, zero exposed legacy IPv4 tables, IPv6 legacy tables not exposed, SSH wildcard listeners in both families, DNS/time-sync/DHCP-related listener ports and forwarding flags were observed. This supersedes the pending/correction boundary below; the failed PR #171 observer must not be retried.

IMG_8933–IMG_8935 at 02:12–02:13 show one visible SSH/TCP rule, a Custom IPv4 /32, browser SSH IPv4 enabled and browser IPv6 unchecked. Private addresses are omitted. Current screenshots do not re-show the port field; earlier configuration and successful Termius use TCP 22. The /32 is a public source address, not a unique-device guarantee; the browser checkbox does not disable host IPv6. Preserve the known manual/template difference. IMG_8936 at 02:16 shows UFW's own `Status: inactive`, despite its loaded/active/enabled systemd unit. Service state is not firewall state. These are user-supplied observations, not an independent Work AWS/SSH session or full effective-policy/reboot qualification.

The [transition proposal and rehearsal](SECRET_CUSTODY_NETWORK_TRANSITION_REVIEW.md) defines a default-deny maintenance fallback and an atomic qualification transition that preserves the same administration paths. It must remove qualification allowances including established flows, preserve unrelated tables, and stop on unknown owned-table drift. No fallback to unrestricted egress or world-open SSH is permitted. The initial maintenance anchor and independently supervised recovery remain unresolved live boundaries.

This development adds fixed synthetic nft profiles and mandatory isolated IPv4/IPv6 packet tests for connection preservation, positive/negative reachability, failed-transaction atomicity, restricted rollback and ownership drift. It is CI-only; it has no live apply path. Exact-head CI and merge evidence belong in the associated PR. Local Work cannot unshare; local guard tests alone do not qualify kernel behavior. TCP-22 echo tests are transport evidence, not authenticated SSH. No live policy was applied or existing phone command repeated.

Initial CI on `224f0be5add39e9cd27770993e8070f3785178b9` stopped while loading the unrelated fixture table, before packet assertions. No live host was involved. The one-line nested nft fixture was replaced with explicit statement/newline boundaries, and bounded synthetic-only command diagnostics were added. The original log did not include nft stderr; do not invent its exact parser message. Require the changed-code kernel run to succeed; no test is skipped or weakened.

Next: implement the bounded private dependency reader and initial-anchor recovery design, then the actual private profiles, independent watchdog and concurrency/ownership guard. Missing inputs include browser-SSH source-range lifecycle and independent recovery, effective upstream DNS/NTP, DHCP/IPv6 control/PMTU dependencies, exact bootstrap/runtime destinations and future policy ownership. Do not invent them, request secrets, repeat general baseline/probes, or widen egress to make tests pass. There is not yet a concrete live apply artifact to approve. H2a authorization does not imply firewall apply.

H1, corrected H2a install and measured H2b/H2c/H2d results remain complete. The H2a placeholder stays inactive. All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Host/cloud hardening, persistence, local IPC/syscall/application capacity, TLS and full controller/reboot recovery remain incomplete. Host remains untrusted / no-secret.

## Historical boundary at 01:56 JST: readback failure and parser correction

Updated: 2026-10-02 01:56 JST evidence (Asia/Tokyo).

The user's IMG_8929 shows the immutable PR #171 observer at commit `60b435c8e2e04d9dc14bbc5070e867cdfa8ad996`, SHA-256 `d94175d03b18fa167fa98b76379d62ef8df178e4a7fe21e899437a93a08ef572`, ending with `STOP NETWORK_READBACK_UNAVAILABLE` and `RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION`, followed by the prompt. This is an unsuccessful host observation. No host facts were emitted; effective network policy remains unknown. The screenshot cannot identify the failed stage or exception type. Do not repeat that unchanged command or claim a host configuration failure.

A concrete observer defect is reproduced locally: `ss` can render scoped IPv6 as `[fe80::1234]%interface:546`. The old `strip("[]").split("%", 1)[0]` leaves a closing bracket and raises ValueError. The iproute2 v6.1.0 source brackets the address before appending the interface scope, confirming that this is a legitimate representation. The original tests exercised only scope inside brackets and real unscoped loopback sockets. This is a verified parser defect and a plausible explanation of the live STOP, **not yet a confirmed live root cause**.

The correction supports both bracket/scope placements and scoped wildcards, while rejecting malformed brackets, duplicate/empty zones and invalid addresses. It also attributes read/parse failures to fixed stage and category codes without exception text, raw addresses or command diagnostics. No read is skipped; facts stay buffered until complete success. The fixed read-only commands, byte/time bounds, no-mutation scope and all disabled gates remain unchanged.

Sixteen offline tests cover the correction and error attribution. Mandatory existing CI adds an actual scope-bearing IPv6 UDP socket inside its disposable isolated network namespace, alongside nft and IPv4/IPv6 checks. All five workflows must pass on the correction commit before merge/readback and a replacement immutable phone command. CI success alone does not resolve the live incident. One changed-code phone run should either complete with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION` or provide a new fixed STOP/STAGE pair; diagnose that pair rather than repeating unchanged commands.

H1, H2a recovery/installation, H2b, H2c and the ten H2d PASS records at 01:38 JST remain completed in their measured scopes (PR #170). Do not repeat provisioning, login/key/keyboard setup, rollback/apply or those completed probes. The H2a placeholder remains inactive. Work has no independent host/AWS session and the user supplies the live terminal evidence.

After one successful host readback, inspect the current Lightsail IPv4 and IPv6 firewall entries from the existing phone session. The earlier SSH edit screenshots did not expose the complete saved policy. Unknown/nonempty host rules require private review; do not flush or replace them. No IAM expansion, new inventory workflow dispatch, firewall change, stress or reboot follows from this correction. Preserve phone SSH and the recorded manual/template difference.

See [network readback review](SECRET_CUSTODY_HOST_NETWORK_READBACK_REVIEW.md). All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Local IPC/syscall, application capacity, complete host/cloud ingress and default-deny egress, TLS, whole-controller and reboot recovery qualification remain pending. The host stays untrusted/no-secret.

## Historical failed H2a attempt and correction: H2a authorized; first apply failed; correction under validation


Updated: 2026-10-02 00:06 JST evidence (Asia/Tokyo).

The user explicitly said `適用して` at 2026-10-01 23:56:43 JST after the exact H2a identity/files/inactive-unit scope was presented. That authorization remains valid for diagnosis, bounded recovery and corrected application within the same scope; **do not ask for the same permission again**. It does not activate runtime, provider, credentials, networking changes or any other gate.

PR #166 merged offline preparation. The user's first live command pinned commit `5cc75aa40523e405ccd0a6515386d3a41eeb886d` and script SHA-256 `50a92a2b0c4585cc965a91faf737d81d337408573cf2668dd26dc49a825473e1`. At 00:00 JST it returned `STOP HOST_COMMAND_FAILED` / `RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_APPLY`. This was **not a successful installation**.

At 00:06 JST screenshot IMG_8924 confirmed: the receipt directory exists; the reserved code/config directories and unit file are absent; dedicated user/group lookups each return 2; systemd reports not-found/inactive, empty fragment/drop-ins/unit-file state, and show exit 0. Receipt contents have not independently been read back. The failure is consistent with the invalid `useradd --key CREATE_MAIL_SPOOL=no` argument found in our implementation. The prior mocked account tests missed the real parser boundary. The correction removes that invalid login.defs override; system accounts already skip mail creation. Fixed stage-specific command errors retain diagnostic privacy.

[H2a review and recovery](SECRET_CUSTODY_HOST_H2A_REVIEW.md) describes the defect, primary source and new real CLI test: installed Ubuntu 24.04 account tools target only a disposable chroot database, while the manager/process adapter remains synthetic. It reproduces the invalid command, checks receipt-only partial state, then exercises bounded rollback, corrected apply and verification. Require this CI step and existing regression checks to pass on the exact correction commit before merge or phone execution. Local Work has only UID/GID 0 and rejects the account CLI audit interface; it cannot substitute for this CI gate.

After CI/merge, use an immutable, hash-checked corrected script. Run its existing ownership-checked rollback once, then apply only if rollback succeeds; verify afterwards. Preserve the existing receipt schema for compatibility. No blind recursive removal, unchanged retry, approval bypass, password/key request or firewall widening. Any new STOP requires diagnosis. Successful offline tests are not live success; await the phone result `INSTALLED_DISABLED_NOT_QUALIFIED` before recording installation.

The candidate remains **untrusted / no-secret**; H2-H7 effective qualification and all runtime/credential gates remain pending/OFF. Work has no independently verified AWS/SSH session. The user's Termius connection works. Do not repeat provisioning, cost approval, IAM/bootstrap, inventory, key import, keyboard setup or H1.

## Previous milestone: creation and H1 completed

Updated: 2026-10-01 23:23 JST (Asia/Tokyo).

The user's phone screenshots confirm completion of the approved single Tokyo candidate and attached static IPv4, successful native Termius SSH login, command execution and the read-only H1 result `PREFLIGHT_OK_NO_MUTATION` with zero warnings/failures. See [creation and H1 evidence](SECRET_CUSTODY_HOST_H1_EVIDENCE.md) for the sanitized chronology, immutable script identity and limits.

The host remains **untrusted / no-secret**. H2-H7, workload capacity, effective sandbox/default-deny egress, static egress, TLS and reboot/recovery qualification are pending. H2a authorization, correction and successful installation are recorded above; effective qualification remains pending. No runtime/provider activation or custody secret use follows from H1.

Do not repeat creation, its cost approval, IAM/bootstrap, inventory, phone browser keyboard attempts, key import or H1 just to resume. The existing phone Termius path works. Work has no independently verified AWS/host session; use existing evidence and connectors within their actual permissions.

The phone administration change added one observed-source IPv4 /32 for SSH while preserving browser SSH IPv4 access. The 02:12–02:13 saved-rule UI evidence above supersedes the earlier pending readback; effective reachability remains unqualified. The original CloudFormation template still describes browser-only ingress. Review this manual difference before any stack update; keep IPs/key material private.

The dated sections below are historical observations at their stated stage. Their earlier zero-resource counts and untested-login statements are superseded by the evidence above, not instructions to repeat those operations.

## Scoped creation authorization (historical; operation now complete) — 2026-10-01 20:56:49 JST

The user replied `続けて` directly to the explicit approval request for the presented candidate file, one Tokyo Ubuntu 24.04 / 1 GB / 2 vCPU / 40 GB instance, USD 7/month base bundle (tax/transfer overage separate), one attached static IPv4, browser-SSH-only initial ingress and retention of successfully created resources on failure. In that conversational context, this authorizes proceeding with that exact one-candidate creation. Do not ask the same cost/configuration question again.

The approved template remains blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its default and repository metadata remain non-authorizing; the live parameter may now be set to `ONE_CANDIDATE_USD7_APPROVED` for this approved operation. Proposed inputs remain stack `keirin-ai-custody-h1`, instance `keirin-custody-h1`, static IP `keirin-custody-h1-ip`, zone `ap-northeast-1a`, blueprint `ubuntu_24_04`, bundle `micro_3_0`, and existing default key `LightsailDefaultKeyPair`.

Authorization is not completion. No CREATE change set, instance, static IP or SSH login has been performed by this turn. The next required evidence is the authenticated intended-account/Tokyo context, absent proposed stack name, current selected blueprint/bundle and the actual resolved change set with exactly two Add actions. Verify preserve-successful-resources and deletion-policy behavior before Execute. A matching actual proposal can proceed under the existing approval; a different scope, cost, account, ingress or failure behavior requires resolving that difference before execution.

The usable AWS session is on the user's phone; Work has no verified AWS control-plane session and the existing GitHub role cannot provision. Guide the existing phone session without retrying the known Work login failure. Do not repeat inventory/bootstrap, expand IAM, create/download keys or introduce extra resources. Hosted execution, real credentials, hardening, Supabase changes and production prediction remain outside this authorization.

## Creation configuration and public-price review — 2026-10-01 (before approval)

At the earlier offline review, the paid scope was fully specified but not yet authorized or executed; subsequent authorization is recorded above. AWS's [current public pricing](https://aws.amazon.com/lightsail/pricing/) was rechecked on 2026-10-01: Linux/Unix with public IPv4, 1 GB memory, 2 vCPU, 40 GB disk and 2 TB transfer is USD 7/month. The [billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html) confirms no additional static-IP charge while attached, and USD 0.005/hour when unattached for more than one hour. Taxes, currency conversion and transfer overage are outside the bundle ceiling; no free-trial credit is assumed.

The exact candidate remains unchanged from main `16c31f91a4205991c28ac2a33e8c64678a2a4f29`, blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its two resources are CustodyCandidate and CustodyStaticIp. The proposed new stack name is `keirin-ai-custody-h1`; stack-name absence and independent account identity are still unverified. The selected zone is `ap-northeast-1a` and the existing key parameter is `LightsailDefaultKeyPair`, observed by inventory run #2. Blueprint/bundle availability evidence remains the 18:28 catalog run; public-price verification is not a new AWS API observation.

At this earlier review point, the cost decision was still pending and the acknowledgement remained NOT_AUTHORIZED. The subsequent 20:56:49 JST authorization is recorded above. The actual CREATE change set and account/stack checks remain pending; do not confuse approval with execution or GitHub authentication with AWS access.

## Corrected inventory verified on 2026-10-01 (historical, before creation)

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

## Verified catalog facts (historical, before creation)

| Item | Observed result |
| --- | --- |
| Region | `ap-northeast-1` available |
| Availability zones | `ap-northeast-1a`, `ap-northeast-1c`, `ap-northeast-1d` |
| Active Ubuntu LTS blueprints | `ubuntu_24_04` (24.04 LTS), `ubuntu_22_04` (22.04 LTS) |
| Matching bundle | `micro_3_0`, Micro, Linux/Unix |
| CPU / RAM / disk | 2 vCPU / 1 GiB / 40 GiB |
| Monthly transfer | 2048 GiB |
| Bundle price | USD 7/month |
| Included public IPv4 | 1 |
| Static IPv4 allocation | Not tested; read-only observation forbids `AllocateStaticIp` |
| Live creation authorization | `false` |

AWS public documentation rechecked on 2026-10-01 states that a static IPv4 attached to a Lightsail instance has no additional charge; an address left unattached for more than one hour costs USD 0.005/hour. Source: [AWS billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html). This is a published pricing rule, not proof that this account can allocate an address.

## Next action and authorization boundary

1. Creation, native SSH and read-only H1 are complete. Use `SECRET_CUSTODY_HOST_H1_EVIDENCE.md`; do not recreate or re-run setup without a changed condition.
2. H2a installation and measured H2b/H2c/H2d verification are complete. H3 dependency observation is also complete; follow the current maintenance design above, not historical phone-run instructions.
3. Confirm complete relevant current firewall rules before H3/H4; preserve the bounded phone/browser administration path. The manual /32 source differs from the original browser-only template.
4. Qualify effective sandbox/resource limits, no-secret capacity, default-deny egress, verified static egress, TLS verify-full and reboot/recovery before introducing custody credentials.
5. Use verified hardened-host egress for separately authorized Supabase network restrictions; verify Data API disabled and SSL enforcement, changing each separately only if required.
6. Require fresh explicit authorization for C2 live DDL, clearly synthetic material for C3, and a separate availability/cost decision and authorization for C4 real credentials.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## Completed AWS bootstrap and root cause

- The user removed the AWS mobile app; Safari subsequently reached Proof of Concept IAM. Earlier browser/app/session hypotheses are historical, not the current blocker.
- Proof of Concept Tokyo CloudFormation returned an explicit SCP deny. The Root-attached `AdvancedModeRegionRestrictionSecurityControlPolicy` had a `RegionFloor` deny whose exception list omitted Tokyo.
- Management-account CloudShell ran read-only `prep.sh` and `review.sh`: `READ-ONLY PREP COMPLETE`, then `REVIEW PASS`.
- Review preserved all non-RegionFloor statements and the original Effect/NotAction/Resource. It retained the original region exceptions globally and added Tokyo only for Proof of Concept. Proposed compact SCP size: 5814 / 10240 characters.
- The user explicitly approved the reviewed policy change. `apply_scp.sh` checked live drift, applied that proposal, read it back and reported `SCP UPDATE VERIFIED`; a rollback copy remained in that CloudShell session.
- Proof of Concept Tokyo CloudFormation then loaded without the SCP error.
- Reviewed stack `keirin-ai-github-oidc-readonly` created exactly `GitHubActionsOidcProvider` and `GitHubLightsailReadOnlyRole`; both reached `CREATE_COMPLETE`.
- The user registered its output as Actions secret `AWS_READONLY_ROLE_ARN`; GitHub confirmed `Repository secret added.`.
- The subsequent successful OIDC workflow independently confirms the read-only role can be assumed. Do not repeat SCP update, stack creation or secret registration.

## Work browser authentication findings

The Work browser initially had no GitHub session. GitHub reported that this account does not support password sign-in. The user selected Google; Google device approval and GitHub emailed device verification then completed, and the authenticated workflow page allowed dispatch. Do not retry unsupported GitHub password sign-in. Browser session persistence is not guaranteed; inspect actual state if UI access is needed again. Do not store credentials, codes, account identifiers or session URLs in the repository. Prefer GitHub connector tools for supported reads/writes; UI was needed only because workflow dispatch was not exposed by the connector.

## Fixed safety state

The runtime and custody restrictions remain unchanged; resource creation and H1 have progressed as recorded above:

- hosted task/provider execution OFF;
- production prediction OFF;
- prediction DB writes OFF;
- automatic external race-data fetching OFF;
- provider generation/write unbound;
- scheduler/recurrence OFF;
- report delivery OFF;
- no real provider/OAuth refresh credential connected or held in custody;
- no C2 live secret-store DDL applied;
- one paid candidate and attached static IPv4 exist; H1 passed, full hardening is pending.

The original catalog workflow made its three catalog reads. The later inventory workflow made the three authorized Tokyo inventory reads after short-lived OIDC authentication. The user separately completed the reviewed IAM update. Neither workflow allocated an IP, created a host/key, downloaded key material, or changed IAM/SCP or Supabase.

## Offline validation and remaining maintenance

PR #152's catalog script suppresses raw AWS CLI stderr and stops on command failure. Its 58 synthetic tests and PR #153's `cfn-lint==1.57.1` validation are historical offline evidence, separate from the successful live run above. Do not copy raw authentication logs into repository evidence; they may contain non-secret but account-specific role identifiers.

The successful run reported an actions/checkout@v4 Node.js 20 deprecation warning and an ubuntu-latest migration notice. These did not fail the run and are maintenance follow-ups, not justification for repeating live observation.

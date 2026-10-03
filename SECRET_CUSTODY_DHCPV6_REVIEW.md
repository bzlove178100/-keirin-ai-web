# Isolated real networkd DHCPv6 lifecycle

Prepared 2026-10-03. Fixed synthetic CI only; no live host or apply artifact.

PR #179 measured RA/SLAAC and kernel ND/DAD. This slice uses a separate fixed
networkd profile to measure actual DHCPv6 IA_NA acquisition, Renew, Rebind and
valid-lifetime expiry under restrictive inet/netdev rules. It retains the
private network/mount/runtime/config isolation and the earlier mandatory jobs.

## Protocol decision

The tested systemd v255 sender uses UDP from its link-local address to
ff02::1:2 for client messages, including Renew. Renew and Rebind are therefore
distinguished by actual message types and server-ID fields, not by assuming
the IPv4 unicast/broadcast pattern. Server responses are unicast to the client.
RFC 9915 obsoletes the former server-unicast capability; this fixture does not
claim conformance of every v255 behavior to the newer specification.

The synthetic server joins the multicast group, reads IPV6_PKTINFO and checks
destination/interface scope, client port, message kind, bounded options,
client identity/IAID and requested IA address. It replies with matching
transaction/client identifiers, a fixed IA_NA address, T1/T2/valid times of
8/24/48 seconds and distinct primary/alternate DUIDs and link-local addresses.
Rapid Commit is disabled so the four-message exchange is required. This is a
minimal local test server, not a production allocator, relay or authenticator.

Periodic RA has the managed flag and an on-link, non-autonomous prefix.
Networkd also disables autonomous prefix use. Thus SLAAC cannot substitute for
a missing DHCPv6 lease. RA continues during DHCP server silence: address expiry
is tested independently of default-route expiry. Administration comes from an
off-link documentation address on the same isolated peer, requiring the RA
route for replies. TCP echo is transport evidence, not authenticated SSH.

## Required acceptance

| Case | Evidence |
| --- | --- |
| Packet controls | Every UDP tuple probe arrives before filtering; afterwards exact one-packet netdev counters and protocol-socket delivery/absence confirm primary/alternate allows and wrong source/destination/ports plus unsupported unicast denial |
| Capture boundary | ETH_P_ALL still observes denied ingress; no privileged capture isolation claim |
| Acquisition | Before managed RA no DHCP events/address; then Solicit/Advertise/Request/Reply, usable real address and RA route, inet/netdev DHCP counters, existing/new administration |
| Client timers | Actual private-client journal must report distinct T1/T2 in the v255 jitter ranges; absent or collapsed timer evidence fails before lifecycle qualification |
| Renew | Actual multicast Renew names primary DUID; replies extend kernel address lifetime and increment both filter-layer counters |
| Rebind | Primary Renew goes unanswered; Rebind omits server ID; alternate replies; the next real Renew names the alternate DUID, proving client adoption; administration survives |
| Expiry | No DHCP replies, including to alternate Renew/Rebind; address disappears, link-local and RA default route remain, and a new administration connection fails |
| Cleanup | Private unit/files, peer, veth and both tables removed; only loopback and an empty ruleset remain |

All fixture events/packets, waits, commands and processes are bounded. Only
the new DHCPv6 client profile has a 195-second unit ceiling; earlier profiles
retain 110 seconds. The CI job ceiling is four minutes. Diagnostics contain
fixed synthetic state and classification, not raw client identifiers or secrets.

## Limits and next work

This is one fixed IA_NA address retained through server change, not renumbering,
prefix delegation, relay, Rapid Commit, legacy unicast, DHCP authentication or
every malformed/forged reply case. Header controls use direct IPv6 next-header
fields; extension headers, fragments, VLANs and arbitrary raw metadata remain
outside the claim. DUIDs and source headers are not security identities.
Two approved server tuples do not implement discovery-to-allowlist widening.

Next qualify IPv4/IPv6 PMTU with an actual constrained intermediate path, then
compose dynamic dependencies with independently supervised restricted recovery.
DNS/time lifecycle, first restricted maintenance installation and wrong shared
allowlist recovery remain incomplete. No live apply, phone retry, AWS/SSH
session, credential or runtime activation. H2a and every runtime/provider/
credential/prediction/DB-write/data-fetch/scheduler/report gate stay OFF.

## Primary sources checked

- [systemd v255 DHCPv6 client](https://github.com/systemd/systemd/blob/v255/src/libsystemd-network/sd-dhcp6-client.c):
  message state/server-ID construction, all_servers UDP send and lease timers.
- [systemd v255 DHCPv6 sockets](https://github.com/systemd/systemd/blob/v255/src/libsystemd-network/dhcp6-network.c):
  AF_INET6 UDP, link-local binding and server port.
- [systemd v255 configuration](https://github.com/systemd/systemd/blob/v255/man/systemd.network.xml):
  managed RA activation, RapidCommit, autonomous prefix and DHCP options.
- [RFC 9915](https://www.rfc-editor.org/rfc/rfc9915.html):
  multicast client/server exchanges, IA_NA, Renew/Rebind and deprecated server
  unicast. Implementation behavior is measured separately from the standard.

Eight new local tests plus four IPv6 and five shared DHCP tests pass. Actual
changed-head CI is required; final-head workflows and any diagnosis belong
in the associated PR. No failed lifecycle stage may be skipped.

## Observed blocker — PR #180 remains unmerged

Initial code head `d92e190d82d6e21669a54ff8dc8e8f897137f9a6` failed
[regression run 37116221040, job 111183444650](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/37116221040/job/111183444650)
on kernel `6.17.0-1022-azure`, networkd `255.4-1ubuntu8.17`.
All twelve existing regression jobs and the four other workflows succeeded.
The DHCPv6 failure is mandatory and prevents integration.

The original 8/18/40-second server replies achieved tuple controls,
four-message acquisition and one primary Renew/lifetime refresh. The peer
then answered Rebind with the alternate DUID. The real client processed those
replies and refreshed the address, but repeatedly entered Rebind without the
required subsequent alternate-DUID Renew. Journal evidence reported both
T1 and T2 as 7 seconds. The wait for alternate Renew failed; expiry and final
cleanup acceptance were not reached. This is not evidence that alternate
replies were filtered or rejected. One observed Renew does not establish
correct automatic timer behavior.

The upstream v255.4 `sd-dhcp6-lease.c` implements the T2 getter using the T1
field. The official Ubuntu `255.4-1ubuntu8.17` packaging archive identifies
that exact version in its changelog; none of its 84 enabled patches changes
`sd-dhcp6-lease.c`. An older applied-source revision from the DHCPv4 diagnosis
was checked but identified itself as 8.11, so it is not the exact-version proof.
The official upstream fix is
[`8f5eaeb143dd9e58503980ae5f63dd78c463180e`](https://github.com/systemd/systemd/commit/8f5eaeb143dd9e58503980ae5f63dd78c463180e)
(2025-07-21): it changes the T2 getter to the T2 field and explicitly explains
skipped renewal. The observed failure agrees with that defect. The checked
Ubuntu archive currently exposes the base and 8.17 source packages for this
255.4 series; neither a corrected package nor a patched client was installed.

Sources inspected read-only:

- [upstream v255.4 lease implementation](https://github.com/systemd/systemd-stable/blob/v255.4/src/libsystemd-network/sd-dhcp6-lease.c)
- [exact Ubuntu packaging archive](https://archive.ubuntu.com/ubuntu/pool/main/s/systemd/systemd_255.4-1ubuntu8.17.debian.tar.xz),
  SHA-256 `4695ff34f83b1f7e6e02bf3cfac2e2a44ac76b6cfc5a38c0081bac6919d547bb`
- [upstream fix patch](https://github.com/systemd/systemd/commit/8f5eaeb143dd9e58503980ae5f63dd78c463180e.patch),
  SHA-256 `b581a4c784a89648f8a8f25866a2b66ad57e54e6644a3ab2c8b6fe75fef86ffb`

The follow-up adds a mandatory real-client timer check. It rejects the known
collapsed T1/T2 pair and missing evidence, even if scheduling happens to emit
Renew. A local wire-format check independently verifies response timers,
transaction/client IDs, alternate DUID and nested address lifetimes.
A separate fixture issue is also corrected: the client permits 10 seconds of
timer coalescing, so T2 is raised to 24 seconds and the lease to 48. The minimum
jittered T2 (21.6) now exceeds maximum T1 (8) by more than that window.
The longer lease only changes this isolated DHCPv6 unit's bound to 195 seconds.
No existing lifecycle assertion or mandatory CI job is skipped or waived.
The next changed-head run checks this explicit rejection, not a claimed fix
of the installed client. Its result must be recorded in PR #180.

Resume from this dependency blocker, not PMTU: obtain or build a
provenance-pinned client containing the official fix entirely in disposable
CI, keep the original unmodified-package failure as a separate result, and
rerun every lifecycle stage. A privately built client would qualify only that
build, not Ubuntu's original binary. Until the target client is explicitly
identified and the full required job plus all five final-head workflows pass,
keep PR #180 draft/unmerged. This diagnostic change does not modify main or
any live host, install packages, change a live firewall or activate a gate.

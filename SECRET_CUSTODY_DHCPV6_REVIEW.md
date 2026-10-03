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
8/18/40 seconds and distinct primary/alternate DUIDs and link-local addresses.
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
| Renew | Actual multicast Renew names primary DUID; replies extend kernel address lifetime and increment both filter-layer counters |
| Rebind | Primary Renew goes unanswered; Rebind omits server ID; alternate replies; the next real Renew names the alternate DUID, proving client adoption; administration survives |
| Expiry | No DHCP replies, including to alternate Renew/Rebind; address disappears, link-local and RA default route remain, and a new administration connection fails |
| Cleanup | Private unit/files, peer, veth and both tables removed; only loopback and an empty ruleset remain |

All fixture events/packets, waits, commands and processes are bounded. Only
the new DHCPv6 client profile has a 165-second unit ceiling; earlier profiles
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

Five new local tests plus four IPv6 and five shared DHCP tests pass. Actual
changed-head CI is required; final-head workflows and any diagnosis belong
in the associated PR. No failed lifecycle stage may be skipped.

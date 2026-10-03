# Isolated IPv6 RA, ND and DAD qualification

Prepared 2026-10-03. Fixed synthetic CI only; no live installer or host policy.

PR #178 completed DHCPv4 lifecycle composition with restricted link rules.
This next slice tests real Ubuntu networkd RA/SLAAC and kernel neighbor/DAD
behavior. DHCPv6, PMTU and composition with independent recovery are separate
remaining cases; this does not complete the IPv6 maintenance matrix.

## Fixture and acceptance

Reuse the guarded private networkd mount/runtime/config launcher with a fixed
IPv6-only configuration. DHCP is disabled in this profile; networkd performs
SLAAC with a fixed synthetic interface token and reads genuine advertisements.
Two disposable namespaces and one veth use documentation global addresses,
fixed local link addresses and no external route. The peer has an address
outside the advertised /64 on the same isolated machine: client responses to
that administration address require the advertised default route. It is not
a forwarding router or an actual SSH server.

Install default-drop netdev ingress/egress and inet policies before networkd
starts. Permit only selected RA/RS/NS/NA tuples with hop limit 255 and code 0,
plus state-checked administration TCP-22. The link rules inspect direct IPv6
next-header fields and intentionally do not qualify extension-header traffic.
No blanket ICMPv6, established-flow allowance or permanent neighbors are used.
Only namespace-local per-interface sysctls are changed.

| Acceptance | Required evidence |
| --- | --- |
| Packet baseline | Correctly checksummed RA/NS/NA and echo probes reach both packet receivers before filtering, including each later rejected variant |
| Header denial | Unexpected source, hop limit 254 and nonzero control code increment the exact drop counter and do not reach ETH_P_IPV6; echo is denied; the all-protocol tap still sees incoming packets |
| Invalid live RA | After networkd startup, rejected RA variants create neither SLAAC address nor default route |
| Real RA and SLAAC | Valid RA creates the fixed SLAAC address, completes DAD and installs the expected protocol-ra default route; administration opens |
| Dynamic ND | Flush both neighbor caches, retain existing/new administration, observe NS/NA counters and rediscovered nonpermanent gateway neighbor |
| RA refresh | Refresh before the original router lifetime; continue checking old/new administration beyond the original expiry deadline |
| Duplicate DAD | Peer already owns the duplicate address; adding it on the client produces actual dadfailed, NS/NA counter increases and EADDRNOTAVAIL on bind; ordinary administration survives |
| RA expiry | With no further advertisements, the default route disappears while the SLAAC address remains; a new off-link administration connection fails; forwarding stays disabled |
| Cleanup | Private client unit/files, peer, veth and both tables are removed; only loopback and an empty ruleset remain |

The new job is mandatory and bounded. Existing DHCPv4, packet boundary,
transition and independently supervised recovery jobs remain required. The
shared launcher retains the same IPv4 configuration by default.

## Limits and next work

Source/port/header restrictions are not neighbor or router authentication.
An authorized-address spoofer, malicious RA options and privileged ETH_P_ALL
capture are outside this claim. The fixture does not validate every malformed
ND option, checksum failure, wrong-interface path, RA redirect, source-MAC
binding, VLAN/extension/fragment behavior or multiple-router transition.
It permits a bounded multicast address class for ND, not arbitrary ICMPv6.
The duplicate-address case is kernel DAD for an explicitly added address;
SLAAC is separately tested through networkd. This is not DHCPv6 evidence.

Next implement the actual DHCPv6 client lifecycle and constrained-path PMTU
tests, then compose dynamic dependencies with the restricted recovery mechanism.
The first restricted maintenance anchor and incorrect shared-allowlist recovery
remain unresolved. No live apply proposal, phone retry, AWS action, secret or
runtime activation is introduced. H2a and every runtime/provider/credential/
prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Primary sources checked

- [systemd v255 network configuration source](https://github.com/systemd/systemd/blob/v255/man/systemd.network.xml):
  IPv6LinkLocalAddressGenerationMode, IPv6DuplicateAddressDetection,
  IPv6AcceptRA Token and DHCPv6Client define the fixed client profile.
- [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861.html), sections 6.1, 6.3 and 7.1–7.2:
  RA validity and lifetime, neighbor solicitation/advertisement behavior.
- [RFC 4862](https://www.rfc-editor.org/rfc/rfc4862.html), section 5.4:
  tentative and duplicate address behavior.
- [Packet boundary review](SECRET_CUSTODY_RAW_PACKET_REVIEW.md):
  ingress filtering does not isolate privileged all-protocol capture.

Three new guard/checksum tests and five shared DHCP guard/parser tests pass
locally. Actual changed-head CI results and any diagnosis belong in the PR;
all five final-head workflows must pass before integration. No local parser
test substitutes for the real networkd/kernel cases above.

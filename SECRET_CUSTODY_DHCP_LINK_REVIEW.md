# DHCPv4 lifecycle under link restrictions

Prepared 2026-10-03. Disposable CI only; no live apply artifact.

PR #176 measured the real networkd lifecycle; PR #177 measured the distinction
between inet and packet-socket paths. This slice composes those two checks in
the existing mandatory `custody-network-dhcpv4` job. It retains the private
network/mount/runtime/config boundaries and all prior lifecycle assertions.

## Policy and required evidence

The fixed synthetic netdev table has default-drop ingress and egress on the
veth client interface. It permits only the fixture's DHCP tuples, narrow ARP
address pairs, administration TCP-22 and DNS/time UDP transport tuples. The
existing inet table still checks transport connection state. Both tables are
installed before networkd starts, remain through lease expiry, and are removed
only during owned fixture cleanup. No static neighbor entries are installed.

| Stage | Required observation |
| --- | --- |
| Unfiltered isolated controls | Every allowed and denied probe reaches both packet receivers before rules; outbound probes also exercise qdisc bypass |
| Packet restrictions | Wrong source/destination/ports, first and noninitial fragments are denied with exactly one matching IPv4 counter increment; zero-source unicast is denied; allowed primary/alternate/broadcast/bootstrap paths still arrive |
| Ingress distinction | Protocol-specific ETH_P_IP is filtered; ETH_P_ALL still sees incoming denied frames, preserving the documented capture boundary |
| Acquisition | Real client gains its lease and DHCP route with DHCP ingress/bootstrap counter increases; actual ARP passes and administration transport opens |
| Unicast renewal | Real server observes renewal; both inet DHCP and link DHCP counters increase; existing and new administration transports survive |
| Rebinding | Unanswered renewal leads to a broadcast request, alternate-server ACK and changed lease server; link counters increase and administration survives |
| Expiry | Server silence removes the address and DHCP route; a new administration connection to the expired address fails |
| Cleanup | Client unit has no MainPID, owned files/veth are removed, peer is reaped, only loopback and an empty ruleset remain |

Packet controls use valid IPv4 headers and unique non-DHCP payloads before the
client starts. They measure header enforcement on the client socket's protocol
path, not rejection of forged lease messages by networkd. DHCP-related IPv4
counters cannot be satisfied by unrelated ARP/IPv6 traffic. The unfiltered
baseline is confined to an empty disposable namespace, never a live fallback.

## Limits and next work

The lease address is fixed and identical across server change; renumbering is
not tested. The small DHCP messages are unfragmented; this intentionally denies
all IPv4 fragments and does not qualify deployments needing fragmented DHCP.
The bootstrap broadcast restriction is a fixture choice, not a universal DHCP
requirement. Header allowlists do not authenticate servers or ARP neighbors.
Privileged ETH_P_ALL capture is not isolated by ingress filtering. Application
raw capabilities must remain absent as established by PR #177.

No DHCP option authenticity, relay, VLAN, arbitrary Ethernet/header consistency,
ARP spoofing resistance, IPv4 address-conflict defense, full DNS/NTP protocol,
authenticated SSH or live-host qualification is claimed. IPv6 DHCP/RA/ND/DAD,
PMTU, dynamic allowlist changes, restricted rollback with this policy, first
maintenance-anchor installation, wrong shared allowlist recovery and reboot
remain future work. Next qualify IPv6 control traffic, then compose dynamic
dependencies with the independent restricted recovery mechanism.

H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/
scheduler/report gate remain OFF. No phone retry, AWS/SSH operation, credential,
host firewall or networkd change is introduced.

## Primary references

- [nftables manual](https://netfilter.org/projects/nftables/manpage.html):
  netdev hooks, protocol metadata and ARP/IP header expressions. Ingress is
  after network taps and before L3 processing.
- [RFC 2131 sections 4.4.4–4.4.5](https://www.rfc-editor.org/rfc/rfc2131.html):
  broadcast/unicast behavior, renewal, rebinding and expiry are distinct states.
- The source-path analysis and measured kernel evidence in
  [PR #177's review](SECRET_CUSTODY_RAW_PACKET_REVIEW.md) remain applicable;
  the new lifecycle result must be measured rather than inferred from it.

Five local DHCP guard/parser tests and three packet checksum/guard tests pass.
Actual changed-head kernel CI is required; final workflow results, diagnoses and
merge receipt belong in the PR. Do not skip failed stages or relax tuple rules
to obtain a passing result.

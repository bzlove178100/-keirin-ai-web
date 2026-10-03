# Packet socket enforcement boundary

Prepared 2026-10-03. Disposable CI only; no host policy or live apply command.

PR #176 established real DHCPv4 lifecycle behavior, but explicitly left packet
socket enforcement unresolved. systemd v255's DHCP discovery/rebinding socket
is AF_PACKET/SOCK_DGRAM bound to ETH_P_IP. It must not be conflated with an
ETH_P_ALL capture socket or an ordinary AF_INET UDP socket.

## Required real-kernel evidence

The new mandatory Ubuntu job uses two disposable network namespaces and a
fixed veth pair with documentation addresses. Receivers are opened before
transmission, valid IP checksums and UDP lengths are checked, and each case
uses a unique synthetic payload with a bounded receive window. The initial
unfiltered **isolated fixture** verifies all receivers and both directions.
It is not a fallback proposed for the live host.

| Case | Required observation |
| --- | --- |
| inet input/output drop | Ordinary UDP is blocked with a counter increment; AF_PACKET send bypasses inet output, and both packet receivers see incoming data before inet input drops it |
| netdev ingress allow | The exact allowed tuple reaches ETH_P_IP and ETH_P_ALL; inet input still blocks its UDP delivery |
| netdev ingress deny | Wrong source/port and fragmented IPv4 are counted and denied to ETH_P_IP; ETH_P_ALL still sees the packet |
| netdev egress | Allowed send reaches the peer; wrong source/destination/port and fragments are counted and absent at all peer receivers, with and without PACKET_QDISC_BYPASS |
| Capability restriction | A separately executed child has zero effective/permitted/inheritable/ambient/bounding capabilities, no_new_privs, and no inherited socket; AF_PACKET and IPv4/IPv6 raw creation return EPERM while ordinary UDP socket creation works |
| Cleanup | Owned peer process is reaped; veth and both fixture tables are removed; only loopback and an empty ruleset remain |

Rule counters for the tested IPv4 packet must increase by exactly one; unrelated
IPv6/ARP traffic cannot satisfy those counter assertions. An ENOBUFS send error
alone is not accepted as evidence of enforcement. Neither missing packets nor
successful rule installation alone qualify the path.

## Decision and limits

Keep packet/raw capabilities out of the application worker. A privileged
network-configuration component is a separate trust boundary, not permission
to give raw sockets to generated application work. Capability removal does
not revoke an already-open socket, which is why the child must also have no
inherited socket. This fixture measures creation refusal after exec; it does
not prove every descriptor-passing, user-namespace, syscall or service path is
confined. Existing H2 sandbox restrictions remain necessary.

netdev ingress is a candidate filter for the protocol-specific DHCP receive
path. It is not a confidentiality boundary against a privileged ETH_P_ALL
listener: the kernel delivers network taps before this hook. No claim of
complete raw-receive filtering, DHCP authentication, resistance to privileged
rule writers, or live-host qualification is made. Address/port fields can be
spoofed and are not server identity authentication.

The fixture uses static neighbors and narrowly fixed UDP tuples. It does not
implement DHCP options, broadcast acquisition, renewal/rebinding under the
new netdev rules, IPv6 RA/ND/DAD, VLANs, PMTU, interface changes, rule ownership
or rollback composition. Positive packet checks are not replacements for
those later lifecycle tests. The next slice should compose restricted link
rules with the existing real DHCP client, retaining its renewal/rebind/expiry
and administration assertions, before extending to IPv6 control traffic.

The unresolved first restricted maintenance anchor and recovery from a wrong
shared allowlist still prevent a live apply proposal. No extra phone evidence,
AWS action, IAM expansion, secrets or live firewall operation is needed here.
H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/
report gates remain OFF.

## Primary sources checked

- [nftables manual](https://netfilter.org/projects/nftables/manpage.html),
  Netdev address family: ingress follows network taps and precedes L3 handling.
- [Linux v6.8 device receive path](https://github.com/torvalds/linux/blob/v6.8/net/core/dev.c):
  `__netif_receive_skb_core` and `nf_ingress` deliver `ptype_all` before ingress;
  protocol-specific handlers run later. CI records its actual running kernel.
- [Linux v6.8 packet socket transmit](https://github.com/torvalds/linux/blob/v6.8/net/packet/af_packet.c):
  `packet_xmit` uses the netdev egress hook even for PACKET_QDISC_BYPASS when
  that hook is configured. Source review alone is not a passed runner test.
- [systemd v255 DHCP socket](https://github.com/systemd/systemd/blob/v255/src/libsystemd-network/dhcp-network.c):
  AF_PACKET/SOCK_DGRAM creation and ETH_P_IP binding.

Local guards/checksum tests must pass, followed by actual CI without skips.
Final-head workflow results and any diagnosed correction belong in the PR.

## Initial CI correction

Head `e5440f430a3456d00d503070b92eaf25d4386daa`, regression run
`37112295809`, job `111172403460`, reached the valid raw packet/receiver
controls on kernel `6.17.0-1022-azure`, then the ordinary UDP denial probe
returned EPERM. The fixture incorrectly let that expected refusal abort the
measurement. [Linux v6.17 netfilter core](https://github.com/torvalds/linux/blob/v6.17/net/netfilter/core.c)
returns -EPERM for a drop verdict without a different explicit error.

The correction first requires ordinary UDP transmission to all peer receivers
before installing inet rules. Afterwards it requires EPERM, exactly one
output-drop counter increment and no peer delivery. Thus an unrelated
permission error cannot count as successful enforcement. The rest of the
packet/capability assertions stay intact; corrected-head CI is required.

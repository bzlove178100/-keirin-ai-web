# Routed IPv4/IPv6 PMTU under restricted policy

Prepared 2026-10-03. Fixed synthetic CI only, never a live installer.

The earlier fixtures do not establish that an allowed management transfer
survives a smaller MTU on its actual route. This mandatory fixture creates
three disposable namespaces per IP family: sender, forwarding kernel router,
and receiver. All links start at 1500. TCP connections are established before
the router's downstream link and receiver link become 1280; the sender's
interface stays at 1500. Only fixed documentation addresses and explicit
endpoint routes exist. Static neighbors isolate PMTU from DHCP/RA/ND.

The sender has default-drop netdev ingress/egress and inet input/output/
forward chains. Only the approved endpoint's TCP/22 transport is allowed.
Two fixed router source addresses may send IPv4 type 3/code 4 or IPv6 type
2/code 0 to the sender. Inet additionally requires conntrack RELATED before
a dedicated PMTU gate. The gate changes only the error verdict; it never
opens TCP/443 or other data paths. The intermediate router is a local kernel
forwarder, not a synthetic packet generator for the positive PMTU case.

## Mandatory evidence per family

| Case | Evidence |
| --- | --- |
| Baseline | Approved TCP/22 and subsequently forbidden TCP/443 both exchange real data through the unconstrained router before filtering |
| Initial state | Two established administration connections; connected IP_MTU/IPV6_MTU and TCP_INFO report 1500, and send MSS exceeds 1280 |
| Wrong error headers | Inject real-checksum wrong-source and wrong-code errors; ETH_P_ALL sees each exact frame while its netdev drop counter rises by one |
| Unrelated quote | Valid outer error with a non-existent source port in the quote passes the link header rule, then hits the inet unrelated-error drop counter |
| Forged sequence | Correct flow tuple with a sequence shifted by half the 32-bit space passes RELATED; Linux OutOfWindowIcmps rises by one and the connection's MTU stays 1500 |
| Real constrained route, error blocked | Kernel router output error counter rises; capture validates type/code, checksum, announced 1280 MTU, real quoted TCP tuple and original length above 1280 (plus IPv4 DF); the inet error drop counter rises; queued large transfer stalls while small existing/new administration still works |
| Same-flow recovery | Admit RELATED errors only; the same socket and queued 65,536 bytes complete exactly, IP_MTU/IPV6_MTU and TCP_INFO become 1280, send MSS decreases, and receiver-captured data packets are unfragmented and at most 1280 bytes with a 1280-byte packet observed |
| Data denial | TCP/443 remains unreachable and its exact endpoint/port drop counter increases after recovery; administration remains usable |
| Cleanup | Both children are terminated/reaped, their namespaces disappear, owned links/tables are removed, sender has only loopback and an empty ruleset |

TCP MTU probing is explicitly disabled in the disposable sender namespace,
so black-hole probing cannot substitute for the PMTU error. TSO/GSO/GRO and
transmit checksum offload are disabled and read back on all four veth devices.
This prevents aggregate packet lengths or incomplete checksum offload state
from masquerading as wire evidence. The protocol/error captures, RPC, process
waits, reads and total CI job are bounded (four minutes for the job).

The kernel sources were checked for forwarding error generation and the TCP
sequence-window check before PMTU updates. Linux UAPI in.h/in6.h/tcp.h define
the connected MTU socket options and TCP_INFO fields used for independent
readback. Four new local guard/header/checksum tests and three existing packet
helper tests pass. Changed-head kernel CI and all five final-head workflows
must pass before integration; exact run IDs/results belong in the PR.

## Limits and next boundary

A correct source header or conntrack RELATED is not authentication. Only the
listed forged cases are tested; an attacker with valid flow/sequence knowledge
is outside this claim. Direct IPv4 without options and IPv6 without extension
headers are the fixed case. No PMTU increase/cache expiry, UDP application
recovery, tunnel/VLAN, renumbering, asymmetrical Internet topology, complete
ICMP validation or live-host qualification is claimed. ETH_P_ALL intentionally
observes ingress before netdev filtering. TCP echo is not authenticated SSH.

This slice is separate from dynamic DHCP/RA state and supervised rollback.
Next compose qualified dynamic controls with independently supervised
restricted recovery. DNS/time lifecycle, a fixed live DHCPv6 deployment
candidate, first restricted maintenance installation and wrong shared allowlist
recovery remain unresolved. No repeated phone operation, AWS/SSH/live host
change, credentials or runtime activation. H2a and every runtime/provider/
credential/prediction/DB-write/data-fetch/scheduler/report gate stay OFF.

## Primary implementation sources checked

- [Linux v6.17 IPv4 forwarding](https://github.com/torvalds/linux/blob/v6.17/net/ipv4/ip_forward.c): actual MTU comparison and fragmentation-needed generation.
- [Linux v6.17 IPv6 forwarding](https://github.com/torvalds/linux/blob/v6.17/net/ipv6/ip6_output.c): actual Packet Too Big generation and output-interface context.
- [Linux v6.17 TCP IPv4 errors](https://github.com/torvalds/linux/blob/v6.17/net/ipv4/tcp_ipv4.c): sequence window validation before tcp_v4_mtu_reduced.
- [Linux v6.17 TCP IPv6 errors](https://github.com/torvalds/linux/blob/v6.17/net/ipv6/tcp_ipv6.c): sequence window validation before tcp_v6_mtu_reduced.

These are reference implementation sources; CI records the actual runner
kernel version and behavior separately. No inference is made about the live
host or every downstream kernel patch from a version string alone.

# Isolated networkd DHCPv4 lifecycle test

Prepared 2026-10-02. CI only; no live host command or firewall installer.

The accepted private report shows DHCPv4 configuration. Fixed-address tests
cannot establish that address renewal or rebinding works. This change runs the
installed Ubuntu 24.04 systemd-networkd client against a minimal local synthetic
DHCP server inside two disposable namespaces. No additional package is needed.

## Executed acceptance cases (require successful CI)

- Acquire a real lease and DHCP default route; read networkd's private lease.
- Observe unicast DHCPREQUEST with ciaddr, without requested-address/server-ID
  options; answer it and require both nft DHCP counters to increase.
- Stop answering unicast renewal; require a broadcast rebind and ACK from the
  alternate synthetic server, then read the changed SERVER_ADDRESS from the
  client's lease. The client address stays constant across the lease-server
  change; this does not test renumbering to a different client address.
- Check existing and newly opened TCP-22 echo connections during these waits.
  Deny TCP-80 and unrelated UDP while DNS/time UDP echo fixtures remain usable.
  These are transport probes, not authenticated SSH or full DNS/NTP protocols.
- Stop all DHCP answers and require expiry to remove the client address and
  DHCP default route. Expiry intentionally ends connectivity; no stale static
  address is substituted to hide this failure.
- Stop the transient client unit, reap processes, remove unique fixture files
  and veth, and confirm only loopback remains.

## Isolation and limits

Execution requires root, GitHub Actions, an explicit fixture flag, systemd PID 1,
an empty disposable network namespace and an empty ruleset. The client service
joins only this namespace. Its private mount namespace has a fresh /run (no
host D-Bus, networkd leases or runtime network configuration), a dedicated
read-only network configuration and masked vendor/host config directories.
Read-only /sys selects networkd's no-udev/container path. The test verifies
the actual namespace identities, hidden bus and mounted configuration.
The existing host networkd unit is never stopped, restarted or reconfigured.

The peer has documentation addresses and a directly connected route only.
The client's default route leads only to that isolated, nonforwarding peer.
The server is an intentionally limited Ethernet BOOTP/DHCP fixture, not a
production DHCP server, lease allocator, relay or authentication mechanism.
Its options, event count and messages are bounded; malformed packets are ignored.
Timers are short (8/16/32 seconds), with process and job deadlines.

Critical limit: systemd's DHCPv4 client uses raw packet sockets for discovery
and rebinding and a UDP socket after binding. An inet input/output firewall
is not complete enforcement for raw packet sockets. Only the unicast renewal
case asserts inet counter passage. Successful rebinding is evidence of client
lifecycle/transport survival, NOT proof that an inet allowlist authenticates or
restricts all DHCP frames. No invalid-peer rejection claim is made here.
Raw-socket/capability and link-layer enforcement need their own design and tests;
do not expand inet rules and call that problem solved.

DHCPv6, RA/ND/DAD, PMTU, renumbering, DNS/NTP lifecycle, unexpected-peer rejection,
composition with qualification rollback, first maintenance-anchor installation,
non-cooperating rule writers and reboot recovery remain unqualified. This
change does not complete the entire maintenance matrix. All runtime/provider/
credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Source review

- [systemd v255 client](https://github.com/systemd/systemd/blob/v255/src/libsystemd-network/sd-dhcp-client.c):
  client_timeout_t2 binds a raw socket; binding switches to UDP; request state
  distinguishes renewal/rebinding and respects supplied T1/T2/lifetime values.
- [systemd v255 networkd entry](https://github.com/systemd/systemd/blob/v255/src/network/networkd.c):
  runtime-directory creation and privilege drop.
- [systemd v255 manager](https://github.com/systemd/systemd/blob/v255/src/network/networkd-manager.c):
  watch-bind connection to the system bus.
- [systemd v255 udev availability](https://github.com/systemd/systemd/blob/v255/src/shared/udev-util.c):
  read-only /sys indicates no udev environment.
- [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html), section 4.4.5:
  renewal/rebinding and lease expiry are distinct behaviors.

Local parser/namespace refusal tests do not substitute for the actual CI run.
CI results and any correction belong in the PR; never skip a failed lifecycle
stage or ask the phone user to diagnose a disposable CI fixture.

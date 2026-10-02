# Isolated networkd DHCPv4 lifecycle test

Updated 2026-10-03. CI only; no live host command or firewall installer.

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
The child refuses the host mount namespace and a shared host /run filesystem
before any mount or runtime write. It uses a fresh read-only sysfs plus a
container marker confined to its private /run. The installed detection helper
must report no container before the marker and container-other afterwards.
The test verifies namespace identities, distinct runtime storage, hidden bus
and mounted configuration. This is a fixture launch prerequisite, not a
substitute for any lease, route, packet or expiry assertion.
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
- [Ubuntu official applied source](https://git.launchpad.net/ubuntu/+source/systemd),
  revision `b7da9ea580f53668cd765dd27d97b272bc4dc482`:
  `debian/patches/Revert-network-if-sys-is-rw-then-udev-should-be-around.patch`
  changes `link_check_initialized()` to use `detect_container() > 0`.
  `src/basic/virt.c` reads `/run/systemd/container` for non-PID-1 processes.
  This downstream patch differs from the previously cited upstream v255
  `udev_available()` condition. Read-only /sys alone is not sufficient for
  Ubuntu link initialization. The local installed 255.4-1ubuntu8.17 binary
  also calls detect_container at this branch; CI prints its own version.
- [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html), section 4.4.5:
  renewal/rebinding and lease expiry are distinct behaviors.

Local parser/namespace refusal tests do not substitute for the actual CI run.
CI results and any correction belong in the PR; never skip a failed lifecycle
stage or ask the phone user to diagnose a disposable CI fixture.

## Resumption correction — 2026-10-03

PR #176 head `796f6cf685022501408551008d2c2b1c4092e28a` failed
in run `36945051624`, job `110645135668`: no initial lease or route,
no DHCP server events, and link pending udev initialization. All other jobs
and four other workflows completed successfully. The earlier read-only-sysfs
change did not solve this; its unconditional explanation above is corrected.

Distribution source identifies a different initialization predicate. This
revision supplies the container identity only inside the verified private
runtime and checks actual detection before/after it. It preserves sysfs,
network/runtime/config isolation, all original lifecycle deadlines, and every
acceptance assertion. Startup/version and bounded journal context remain
available if another stage fails. Five offline refusal/parser tests pass.
Actual Ubuntu lifecycle CI is still required before claiming the repair worked.
